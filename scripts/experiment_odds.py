    import pandas as pd
import numpy as np
import lightgbm as lgb
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import accuracy_score
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.features.data_loader import load_match_level_data
from app.features.pipeline import engineer_over_under_2_5_features, engineer_btts_features

def train_eval(df, features, target):
    X = df[features].fillna(0)
    y = df[target]
    tscv = TimeSeriesSplit(n_splits=5)
    scores = []
    
    params = {
        'objective': 'binary',
        'metric': 'binary_logloss',
        'boosting_type': 'gbdt',
        'verbose': -1
    }
    
    for train_idx, val_idx in tscv.split(X):
        X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
        y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]
        
        train_data = lgb.Dataset(X_train, label=y_train)
        val_data = lgb.Dataset(X_val, label=y_val, reference=train_data)
        
        model = lgb.train(params, train_data, num_boost_round=100, 
                          valid_sets=[val_data],
                          callbacks=[lgb.early_stopping(10, verbose=False)])
        
        y_pred = model.predict(X_val)
        acc = accuracy_score(y_val, (y_pred > 0.5).astype(int))
        scores.append(acc)
        
    return np.mean(scores)

def run_experiment():
    print("Loading data...")
    match_df = load_match_level_data()
    
    # --- Over/Under 2.5 Experiment ---
    print("\n--- Over/Under 2.5 Experiment ---")
    df_ou = engineer_over_under_2_5_features(match_df)
    df_ou = df_ou[df_ou['over_2_5'].notna()]
    
    # Identify feature columns
    exclude = ['date', 'Date', 'Div', 'Time', 'HomeTeam', 'AwayTeam', 
               'FTHG', 'FTAG', 'FTR', 'HTHG', 'HTAG', 'HTR',
               'home_team', 'away_team', 'home_score', 'away_score',
               'home_half_time_goals', 'away_half_time_goals',
               'home_shots', 'away_shots', 'home_shots_on_target', 'away_shots_on_target',
               'home_corners', 'away_corners', 'home_fouls', 'away_fouls',
               'home_yellow_cards', 'away_yellow_cards', 'home_red_cards', 'away_red_cards',
               'odds_home', 'odds_draw', 'odds_away', 'odds_over_2_5', 'odds_under_2_5',
               'odds_btts_yes', 'odds_btts_no',
               'total_goals', 'over_2_5', 'btts', 'year']
    features_all = [c for c in df_ou.columns if c not in exclude and df_ou[c].dtype in [np.float64, np.int64]]
    
    # 1. With Odds
    print(f"Training WITH Odds (implied_prob_over)...")
    acc_with = train_eval(df_ou, features_all, 'over_2_5')
    print(f"Accuracy: {acc_with:.4f}")
    
    # 2. Without Odds
    features_no_odds = [f for f in features_all if 'implied_prob' not in f and 'odds' not in f]
    print(f"Training WITHOUT Odds...")
    acc_without = train_eval(df_ou, features_no_odds, 'over_2_5')
    print(f"Accuracy: {acc_without:.4f}")
    
    print(f"Impact of Odds: {acc_with - acc_without:.4f}")

    # --- BTTS Experiment ---
    print("\n--- BTTS Experiment ---")
    df_btts = engineer_btts_features(match_df)
    df_btts = df_btts[df_btts['btts'].notna()]
    
    # Manually add odds features for experiment
    if 'odds_btts_yes' in df_btts.columns:
        df_btts['implied_prob_btts'] = 1.0 / df_btts['odds_btts_yes'].replace(0, np.nan).fillna(2.0)
    
    features_btts_base = [c for c in df_btts.columns if c not in exclude and df_btts[c].dtype in [np.float64, np.int64]]
    # Ensure implied_prob is not in base if it wasn't there before (it wasn't)
    features_btts_no_odds = [f for f in features_btts_base if 'implied_prob' not in f and 'odds' not in f]
    
    # 1. Without Odds (Current State)
    print(f"Training WITHOUT Odds (Current)...")
    acc_btts_no = train_eval(df_btts, features_btts_no_odds, 'btts')
    print(f"Accuracy: {acc_btts_no:.4f}")
    
    # 2. With Odds
    features_btts_with = features_btts_no_odds + ['implied_prob_btts']
    print(f"Training WITH Odds...")
    acc_btts_with = train_eval(df_btts, features_btts_with, 'btts')
    print(f"Accuracy: {acc_btts_with:.4f}")
    
    print(f"Impact of Odds: {acc_btts_with - acc_btts_no:.4f}")

if __name__ == "__main__":
    run_experiment()
