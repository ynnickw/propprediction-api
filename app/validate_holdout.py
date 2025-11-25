import pandas as pd
import numpy as np
import lightgbm as lgb
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import PoissonRegressor
from sklearn.metrics import mean_squared_error, mean_absolute_error
import structlog
import os

logger = structlog.get_logger()

DATA_FILE = "data/player_stats_history_enriched.csv"
OUTPUT_FILE = "data/validation_results.csv"

def prepare_features(df):
    """
    Replicate feature engineering from train.py
    """
    df = df.copy()
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values(['player_id', 'date'])
    
    # 1. Create 'is_striker' from position
    if 'position' in df.columns:
        df['is_striker'] = df['position'].apply(lambda x: 1 if x == 'F' else 0)
    else:
        df['is_striker'] = 0
        
    # 2. Rolling Averages for Player Performance
    player_cols = ['shots', 'shots_on_target', 'goals', 'assists', 'minutes']
    for col in player_cols:
        if col in df.columns:
            df[f'{col}_ema_5'] = df.groupby('player_id')[col].transform(lambda x: x.ewm(span=5).mean().shift(1))
            df[f'{col}_last_5'] = df.groupby('player_id')[col].transform(lambda x: x.rolling(5, min_periods=1).mean().shift(1))

    # 3. Team Strength Features (Rolling)
    if 'HS' in df.columns and 'AS' in df.columns:
        df['team_shots'] = np.where(df['is_home'] == 1, df['HS'], df['AS'])
        df['opp_shots'] = np.where(df['is_home'] == 1, df['AS'], df['HS'])
        
        df['team_shots_avg'] = df.groupby('team')['team_shots'].transform(lambda x: x.rolling(10, min_periods=1).mean().shift(1))
        df['opp_conceded_shots_avg'] = df.groupby('opponent')['opp_shots'].transform(lambda x: x.rolling(10, min_periods=1).mean().shift(1))
    else:
        df['team_shots_avg'] = 12.0
        df['opp_conceded_shots_avg'] = 12.0

    # Rating
    if 'rating' in df.columns:
        df['rating_last_5'] = df.groupby('player_id')['rating'].transform(lambda x: x.rolling(5, min_periods=1).mean().shift(1))
    else:
        df['rating_last_5'] = 0

    df = df.fillna(0)
    return df

def train_and_validate(prop_type, df):
    logger.info(f"Validating {prop_type}...")
    
    target_col = prop_type
    if target_col not in df.columns:
        logger.warning(f"Target {target_col} not found in dataset.")
        return None

    # Features (Must match train.py)
    features = [
        'shots_ema_5', 'shots_last_5',
        'shots_on_target_ema_5', 'shots_on_target_last_5',
        'goals_last_5', 'assists_last_5',
        'is_striker', 'minutes_last_5', 
        'rating_last_5',
        'is_home', 
        'team_shots_avg', 'opp_conceded_shots_avg',
        'B365H', 'B365D', 'B365A'
    ]
    
    # Filter valid features
    features = [f for f in features if f in df.columns]
    
    # Split Data (Last 5% as Test)
    # Ensure sorted by date
    df = df.sort_values('date')
    
    n_total = len(df)
    n_test = int(n_total * 0.05)
    n_train = n_total - n_test
    
    train_df = df.iloc[:n_train]
    test_df = df.iloc[n_train:]
    
    X_train = train_df[features]
    y_train = train_df[target_col]
    X_test = test_df[features]
    y_test = test_df[target_col]
    
    logger.info(f"Train size: {len(X_train)}, Test size: {len(X_test)}")
    
    # 1. LightGBM
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
        'verbose': -1,
        'seed': 42
    }
    
    gbm = lgb.train(
        params,
        lgb_train,
        num_boost_round=500,
        valid_sets=[lgb_eval],
        callbacks=[lgb.early_stopping(stopping_rounds=50), lgb.log_evaluation(0)]
    )
    
    # 2. Poisson Regressor
    pipeline = Pipeline([
        ('scaler', StandardScaler()),
        ('poisson', PoissonRegressor(alpha=1.0, max_iter=1000))
    ])
    pipeline.fit(X_train, y_train)
    
    # Predict
    pred_lgb = gbm.predict(X_test, num_iteration=gbm.best_iteration)
    pred_pois = pipeline.predict(X_test)
    pred_ensemble = (pred_lgb + pred_pois) / 2
    
    # Metrics
    rmse = np.sqrt(mean_squared_error(y_test, pred_ensemble))
    mae = mean_absolute_error(y_test, pred_ensemble)
    
    logger.info(f"{prop_type} - RMSE: {rmse:.4f}, MAE: {mae:.4f}")
    
    # Return results for saving
    results = test_df[['date', 'player_name', 'team', 'opponent']].copy()
    results['prop'] = prop_type
    results['actual'] = y_test
    results['prediction'] = pred_ensemble
    results['error'] = results['prediction'] - results['actual']
    
    return results

def main():
    if not os.path.exists(DATA_FILE):
        logger.error(f"Data file {DATA_FILE} not found.")
        return

    logger.info("Loading data...")
    df = pd.read_csv(DATA_FILE)
    
    # Feature Engineering
    logger.info("Preparing features...")
    df = prepare_features(df)
    
    all_results = []
    
    props = ['shots', 'shots_on_target', 'goals', 'assists']
    
    for prop in props:
        res = train_and_validate(prop, df)
        if res is not None:
            all_results.append(res)
            
    if all_results:
        final_df = pd.concat(all_results)
        final_df.to_csv(OUTPUT_FILE, index=False)
        logger.info(f"Validation results saved to {OUTPUT_FILE}")
        
        # Summary
        summary = final_df.groupby('prop').apply(
            lambda x: pd.Series({
                'RMSE': np.sqrt(mean_squared_error(x['actual'], x['prediction'])),
                'MAE': mean_absolute_error(x['actual'], x['prediction'])
            })
        )
        print("\nValidation Summary (Last 5% Holdout):")
        print(summary)

if __name__ == "__main__":
    main()
