import lightgbm as lgb
import pandas as pd
import numpy as np
import os
import joblib
import requests
from io import StringIO
from sklearn.model_selection import TimeSeriesSplit
from sklearn.linear_model import PoissonRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import mean_squared_error, mean_poisson_deviance
import structlog

logger = structlog.get_logger()

MODEL_DIR = "models"
DATA_DIR = "data"
os.makedirs(MODEL_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

# Public data sources (Football-Data.co.uk)
DATA_URLS = {
    "E0_2324": "https://www.football-data.co.uk/mmz4281/2324/E0.csv", # Premier League
    "D1_2324": "https://www.football-data.co.uk/mmz4281/2324/D1.csv", # Bundesliga
    # Add more seasons/leagues as needed
}

def download_data():
    """Download historical match data."""
    dfs = []
    for key, url in DATA_URLS.items():
        filepath = os.path.join(DATA_DIR, f"{key}.csv")
        if not os.path.exists(filepath):
            logger.info(f"Downloading {key} from {url}...")
            try:
                response = requests.get(url)
                response.raise_for_status()
                with open(filepath, "wb") as f:
                    f.write(response.content)
            except Exception as e:
                logger.error(f"Failed to download {url}: {e}")
                continue
        
        try:
            df = pd.read_csv(filepath)
            df['League'] = key[:2]
            dfs.append(df)
        except Exception as e:
            logger.error(f"Failed to read {filepath}: {e}")

    if not dfs:
        raise ValueError("No data available for training.")
    
    return pd.concat(dfs, ignore_index=True)

def prepare_training_data(raw_df: pd.DataFrame, prop_type: str):
    """
    Transform raw match data into player-prop features.
    Note: Public match data often lacks granular player stats (shots, tackles).
    For a TRUE high-end model, we would need player-level logs (e.g., from FBref or API-Football).
    
    Since we are building the PIPELINE, we will assume the raw_df *contains* or is merged with
    player stats. For this script to be runnable without a paid FBref scraper, 
    we will simulate the player-level aggregation from the team-level match data 
    (e.g. assuming team shots are distributed among players) OR 
    we strictly define the schema expected from a player-stats CSV.
    
    Here, we define the schema for a 'player_match_log.csv' which you would populate 
    with real data from your provider.
    """
    
    # In a real high-end app, you'd load a consolidated CSV of player match logs
    # e.g., columns: [date, player_id, team, opponent, minutes, shots, sot, assists, ...]
    
    # For demonstration of the HIGH-END PIPELINE, we will generate a synthetic 
    # player-level dataset derived from the real team stats to show the feature engineering logic.
    # IN PRODUCTION: Replace this generator with `pd.read_csv('player_stats_history.csv')`
    
    logger.info("Generating feature set from match data...")
    
    # Synthetic expansion: Create 11 players per team per match
    player_rows = []
    for _, match in raw_df.iterrows():
        try:
            date = pd.to_datetime(match['Date'], dayfirst=True)
            home_team = match['HomeTeam']
            away_team = match['AwayTeam']
            
            # Team stats
            hs = match.get('HS', 10) # Home Shots
            hst = match.get('HST', 4) # Home Shots on Target
            as_ = match.get('AS', 8) # Away Shots
            ast = match.get('AST', 3) # Away Shots on Target
            
            # Generate dummy players for Home Team
            for i in range(1, 12):
                player_rows.append({
                    'date': date,
                    'player_id': f"{home_team}_{i}",
                    'team': home_team,
                    'opponent': away_team,
                    'is_home': 1,
                    'minutes': 90 if i < 8 else 45, # Simple minutes assumption
                    'shots': max(0, int(np.random.poisson(hs / 11))), # Distribute team shots
                    'shots_on_target': max(0, int(np.random.poisson(hst / 11))),
                    'assists': 0, # Placeholder
                    'cards': 0 # Placeholder
                })
                
            # Generate dummy players for Away Team
            for i in range(1, 12):
                player_rows.append({
                    'date': date,
                    'player_id': f"{away_team}_{i}",
                    'team': away_team,
                    'opponent': home_team,
                    'is_home': 0,
                    'minutes': 90 if i < 8 else 45,
                    'shots': max(0, int(np.random.poisson(as_ / 11))),
                    'shots_on_target': max(0, int(np.random.poisson(ast / 11))),
                    'assists': 0,
                    'cards': 0
                })
        except Exception:
            continue
            
    df = pd.DataFrame(player_rows)
    df = df.sort_values(['player_id', 'date'])
    
    # --- REAL FEATURE ENGINEERING ---
    
    # 1. Rolling Averages (Exponential Weighted for recency bias)
    cols_to_roll = ['shots', 'shots_on_target']
    for col in cols_to_roll:
        df[f'{col}_ema_5'] = df.groupby('player_id')[col].transform(lambda x: x.ewm(span=5).mean().shift(1))
        df[f'{col}_ema_10'] = df.groupby('player_id')[col].transform(lambda x: x.ewm(span=10).mean().shift(1))
    
    # 2. Opponent Strength (Defensive)
    # Calculate how many shots/sot opponents concede on average
    opp_stats = df.groupby('opponent')[cols_to_roll].transform(lambda x: x.rolling(window=10, min_periods=1).mean().shift(1))
    df[[f'opp_conceded_{c}' for c in cols_to_roll]] = opp_stats
    
    # 3. Rest Days
    df['prev_date'] = df.groupby('player_id')['date'].shift(1)
    df['rest_days'] = (df['date'] - df['prev_date']).dt.days.fillna(7)
    
    # Drop NaNs created by shifting
    df = df.dropna()
    
    # Select features and target
    features = [
        'is_home', 'minutes', 'rest_days',
        'shots_ema_5', 'shots_ema_10',
        'shots_on_target_ema_5', 'shots_on_target_ema_10',
        'opp_conceded_shots', 'opp_conceded_shots_on_target'
    ]
    
    target_map = {
        'shots': 'shots',
        'shots_on_target': 'shots_on_target',
        'assists': 'assists',
        'cards': 'cards'
    }
    
    target_col = target_map.get(prop_type)
    if not target_col:
        raise ValueError(f"Unknown prop type: {prop_type}")
        
    return df[features], df[target_col]

def train_ensemble(prop_type: str):
    logger.info(f"Starting training for {prop_type}")
    
    # 1. Load Data
    raw_df = download_data()
    X, y = prepare_training_data(raw_df, prop_type)
    
    # 2. Time Series Split (Strictly train on past, test on future)
    tscv = TimeSeriesSplit(n_splits=5)
    
    lgb_models = []
    poisson_models = []
    scores = []
    
    for train_index, test_index in tscv.split(X):
        X_train, X_test = X.iloc[train_index], X.iloc[test_index]
        y_train, y_test = y.iloc[train_index], y.iloc[test_index]
        
        # --- Model A: LightGBM (Gradient Boosting) ---
        lgb_train = lgb.Dataset(X_train, y_train)
        lgb_eval = lgb.Dataset(X_test, y_test, reference=lgb_train)
        
        params = {
            'objective': 'poisson', # Better for count data than regression
            'metric': 'rmse',
            'boosting_type': 'gbdt',
            'num_leaves': 31,
            'learning_rate': 0.05,
            'feature_fraction': 0.9,
            'bagging_fraction': 0.8,
            'bagging_freq': 5,
            'verbose': -1
        }
        
        gbm = lgb.train(
            params,
            lgb_train,
            num_boost_round=1000,
            valid_sets=[lgb_eval],
            callbacks=[lgb.early_stopping(stopping_rounds=50)]
        )
        lgb_models.append(gbm)
        
        # --- Model B: Poisson Regression (Linear Baseline) ---
        # Good for capturing linear relationships and acting as a stabilizer
        pipeline = Pipeline([
            ('scaler', StandardScaler()),
            ('poisson', PoissonRegressor(alpha=1.0, max_iter=1000))
        ])
        pipeline.fit(X_train, y_train)
        poisson_models.append(pipeline)
        
        # Evaluate Ensemble
        pred_lgb = gbm.predict(X_test, num_iteration=gbm.best_iteration)
        pred_pois = pipeline.predict(X_test)
        pred_ensemble = (pred_lgb + pred_pois) / 2
        
        rmse = np.sqrt(mean_squared_error(y_test, pred_ensemble))
        scores.append(rmse)
        logger.info(f"Fold RMSE: {rmse:.4f}")

    logger.info(f"Average RMSE: {np.mean(scores):.4f}")
    
    # 3. Retrain on full dataset
    logger.info("Retraining on full dataset...")
    
    # LightGBM
    full_lgb_train = lgb.Dataset(X, y)
    final_gbm = lgb.train(
        params,
        full_lgb_train,
        num_boost_round=int(gbm.best_iteration * 1.2) # Train a bit longer on full data
    )
    final_gbm.save_model(os.path.join(MODEL_DIR, f"lgbm_{prop_type}.txt"))
    
    # Poisson
    final_pipeline = Pipeline([
        ('scaler', StandardScaler()),
        ('poisson', PoissonRegressor(alpha=1.0, max_iter=1000))
    ])
    final_pipeline.fit(X, y)
    joblib.dump(final_pipeline, os.path.join(MODEL_DIR, f"poisson_{prop_type}.joblib"))
    
    logger.info(f"Models saved for {prop_type}")

if __name__ == "__main__":
    props = ['shots', 'shots_on_target'] # Extend as needed
    for prop in props:
        train_ensemble(prop)
