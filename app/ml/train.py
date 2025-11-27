import lightgbm as lgb
import pandas as pd
import numpy as np
import os
import joblib
from sklearn.model_selection import TimeSeriesSplit
from sklearn.linear_model import PoissonRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import mean_squared_error
import structlog

logger = structlog.get_logger()

MODEL_DIR = "models"
DATA_DIR = "data"
ENRICHED_DATA_FILE = os.path.join(DATA_DIR, "player_stats_history_enriched.csv")

os.makedirs(MODEL_DIR, exist_ok=True)

def load_data():
    """Load the enriched player dataset."""
    if not os.path.exists(ENRICHED_DATA_FILE):
        raise FileNotFoundError(f"Enriched data file not found at {ENRICHED_DATA_FILE}. Run app.prepare_full_dataset first.")
    
    logger.info(f"Loading enriched data from {ENRICHED_DATA_FILE}...")
    df = pd.read_csv(ENRICHED_DATA_FILE)
    df['date'] = pd.to_datetime(df['date'])
    return df

def prepare_training_data(df: pd.DataFrame, prop_type: str):
    """
    Prepare features and target for training.
    """
    logger.info("Preparing training features...")
    
    # Sort by date for time-series splitting
    df = df.sort_values(['player_id', 'date'])
    
    # --- FEATURE ENGINEERING ---
    
    # 0. Metadata Features (already in enriched file, but ensure types)
    # 0. Metadata Features (already in enriched file, but ensure types)
    # Note: is_striker is derived later from position
    # age, height, market_value are not available in current dataset

    # 1. Rolling Averages (Exponential Weighted for recency bias)
    cols_to_roll = ['shots', 'shots_on_target', 'goals', 'assists']
    for col in cols_to_roll:
        # EMA 5 and 10
        df[f'{col}_ema_5'] = df.groupby('player_id')[col].transform(lambda x: x.ewm(span=5).mean().shift(1))
        df[f'{col}_ema_10'] = df.groupby('player_id')[col].transform(lambda x: x.ewm(span=10).mean().shift(1))
        
        # Recent sums (last 5 games)
        df[f'{col}_last_5'] = df.groupby('player_id')[col].transform(lambda x: x.rolling(5).sum().shift(1))

    # 2. Player Characteristics
    df['avg_minutes_last_5'] = df.groupby('player_id')['minutes'].transform(lambda x: x.rolling(5).mean().shift(1))
    
    # Shot accuracy (cumulative)
    df['cum_shots'] = df.groupby('player_id')['shots'].cumsum().shift(1)
    df['cum_sot'] = df.groupby('player_id')['shots_on_target'].cumsum().shift(1)
    df['shot_accuracy'] = (df['cum_sot'] / df['cum_shots']).fillna(0)
    
    # Goals per 90 (cumulative)
    df['cum_goals'] = df.groupby('player_id')['goals'].cumsum().shift(1)
    df['cum_minutes'] = df.groupby('player_id')['minutes'].cumsum().shift(1)
    df['goals_per_90'] = (df['cum_goals'] / (df['cum_minutes'] / 90)).fillna(0)

    # 3. Team Strength
    team_stats = df.groupby(['team', 'date'])[cols_to_roll].sum().reset_index()
    team_stats['team_shots_avg'] = team_stats.groupby('team')['shots'].transform(lambda x: x.rolling(10).mean().shift(1))
    team_stats['team_goals_avg'] = team_stats.groupby('team')['goals'].transform(lambda x: x.rolling(10).mean().shift(1))
    df = pd.merge(df, team_stats[['team', 'date', 'team_shots_avg', 'team_goals_avg']], on=['team', 'date'], how='left')

    # 4. Home/Away Splits
    df['shots_home_avg'] = df[df['is_home']==1].groupby('player_id')['shots'].transform(lambda x: x.rolling(10).mean().shift(1))
    df['shots_away_avg'] = df[df['is_home']==0].groupby('player_id')['shots'].transform(lambda x: x.rolling(10).mean().shift(1))
    df['shots_home_avg'] = df.groupby('player_id')['shots_home_avg'].ffill()
    df['shots_away_avg'] = df.groupby('player_id')['shots_away_avg'].ffill()

    # 5. Opponent Stats
    opp_stats = df.groupby(['opponent', 'date'])[cols_to_roll].sum().reset_index()
    opp_stats['opp_conceded_shots'] = opp_stats.groupby('opponent')['shots'].transform(lambda x: x.rolling(10).mean().shift(1))
    opp_stats['opp_conceded_shots_on_target'] = opp_stats.groupby('opponent')['shots_on_target'].transform(lambda x: x.rolling(10).mean().shift(1))
    df = pd.merge(df, opp_stats[['opponent', 'date', 'opp_conceded_shots', 'opp_conceded_shots_on_target']], on=['opponent', 'date'], how='left')

    # Vs Specific Opponent History
    df['vs_opponent_shots_avg'] = df.groupby(['player_id', 'opponent'])['shots'].transform(lambda x: x.rolling(5).mean().shift(1))

    # 6. Fatigue / Schedule
    df['prev_date'] = df.groupby('player_id')['date'].shift(1)
    df['rest_days'] = (df['date'] - df['prev_date']).dt.days.fillna(7)
    df['games_in_last_7_days'] = df.groupby('player_id')['date'].transform(
        lambda x: x.diff().dt.days.fillna(7).rolling(window=3).apply(lambda d: (d < 7).sum())
    )

    # 7. External Data Features (Odds & Match Stats)
    # Fill missing external data with 0 or median
    ext_cols = [
        'HS', 'AS', 'HST', 'AST', 'HC', 'AC', 'HF', 'AF', 
        'HY', 'AY', 'HR', 'AR', 'B365H', 'B365D', 'B365A'
    ]
    for col in ext_cols:
        if col in df.columns:
            df[col] = df[col].fillna(df[col].median()).fillna(0)
    
    # Feature Engineering
    # ---------------------------------------------------------
    
    # 1. Create 'is_striker' from position
    if 'position' in df.columns:
        df['is_striker'] = df['position'].apply(lambda x: 1 if x == 'F' else 0)
    else:
        df['is_striker'] = 0
        
    # 2. Rolling Averages for Player Performance
    # Sort by player and date
    df = df.sort_values(['player_id', 'date'])
    
    # Calculate EMAs for player stats
    player_cols = ['shots', 'shots_on_target', 'goals', 'assists', 'minutes']
    for col in player_cols:
        if col in df.columns:
            df[f'{col}_ema_5'] = df.groupby('player_id')[col].transform(lambda x: x.ewm(span=5).mean())
            df[f'{col}_last_5'] = df.groupby('player_id')[col].transform(lambda x: x.rolling(5, min_periods=1).mean())

    # 3. Team Strength Features (Rolling)
    # We use the external match stats (HS, AS, etc.) to calculate team strength
    # BUT we must shift them so we don't use the current match's stats
    
    # Calculate team shots average (using HS/AS from previous matches)
    # This requires careful handling of home/away teams
    df['team_shots'] = np.where(df['is_home'] == 1, df['HS'], df['AS'])
    df['opp_shots'] = np.where(df['is_home'] == 1, df['AS'], df['HS']) # Opponent's shots in this match
    
    # Calculate rolling averages for team shots and opponent shots conceded
    df['team_shots_avg'] = df.groupby('team')['team_shots'].transform(lambda x: x.rolling(10, min_periods=1).mean().shift(1))
    df['opp_conceded_shots_avg'] = df.groupby('opponent')['opp_shots'].transform(lambda x: x.rolling(10, min_periods=1).mean().shift(1))

    # Add rating_last_5 if 'rating' column exists
    if 'rating' in df.columns:
        df['rating_last_5'] = df.groupby('player_id')['rating'].transform(lambda x: x.rolling(5, min_periods=1).mean().shift(1))
    else:
        df['rating_last_5'] = 0 # Default to 0 if rating is not available

    # Drop NaNs created by shifting and rolling
    df = df.fillna(0)
    
    # Select features and target
    features = [
        # Player form
        'shots_ema_5', 'shots_last_5',
        'shots_on_target_ema_5', 'shots_on_target_last_5',
        'goals_last_5', 'assists_last_5',
        
        # Player characteristics
        'is_striker', 'minutes_last_5', 
        'rating_last_5', # derived if rating exists
        
        # Match context
        'is_home', 
        
        # Team/Opponent Rolling Stats (to be created below)
        'team_shots_avg', 'opp_conceded_shots_avg',
        
        # External Data (Odds & Match Stats)
        'B365H', 'B365D', 'B365A', 
        'implied_prob_home', 'implied_prob_away', 'is_favorite',
        # NOTE: We DO NOT include HS, AS, HST, AST, HC, AC here as features.
        # Those are "future" stats for the match being predicted.
        # We only use them to calculate the rolling averages (team_shots_avg, etc.) above.
    ]
    
    # Filter features that actually exist in df
    features = [f for f in features if f in df.columns]
    
    logger.info(f"Training with {len(features)} features: {features}")
    
    target_map = {
        'shots': 'shots',
        'shots_on_target': 'shots_on_target',
        'assists': 'assists',
        'cards': 'cards',
        'goals': 'goals'
    }
    
    target_col = target_map.get(prop_type)
    if not target_col:
        raise ValueError(f"Unknown prop type: {prop_type}")

    # Save intermediate dataset for inspection
    debug_file = os.path.join("data", f"feature_engineered_dataset_{target_col}.csv")
    df.to_csv(debug_file, index=False)
    logger.info(f"Saved feature-engineered dataset to {debug_file}")
        
    return df[features], df[target_col]

def train_ensemble(prop_type: str):
    logger.info(f"Starting training for {prop_type}")
    
    # 1. Load Data
    raw_df = load_data()
    X, y = prepare_training_data(raw_df, prop_type)
    
    logger.info(f"Training with {X.shape[1]} features on {X.shape[0]} samples")
    
    # 2. Time Series Split
    tscv = TimeSeriesSplit(n_splits=5)
    
    lgb_models = []
    poisson_models = []
    scores = []
    
    for train_index, test_index in tscv.split(X):
        X_train, X_test = X.iloc[train_index], X.iloc[test_index]
        y_train, y_test = y.iloc[train_index], y.iloc[test_index]
        
        # --- Model A: LightGBM ---
        lgb_train = lgb.Dataset(X_train, y_train)
        lgb_eval = lgb.Dataset(X_test, y_test, reference=lgb_train)
        
        params = {
            'objective': 'poisson',
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
        
        # --- Model B: Poisson Regression ---
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
        num_boost_round=int(gbm.best_iteration * 1.2)
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
    props = ['shots', 'shots_on_target', 'goals', 'assists']
    for prop in props:
        train_ensemble(prop)
