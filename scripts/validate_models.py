import pandas as pd
import numpy as np
import lightgbm as lgb
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.features.data_loader import load_match_level_data
from app.features.pipeline import engineer_over_under_2_5_features, engineer_btts_features

def validate_model(name, df, features, target):
    print(f"\n{'='*20} Validating {name} {'='*20}")
    
    X = df[features].fillna(0)
    y = df[target]
    
    tscv = TimeSeriesSplit(n_splits=5)
    
    metrics = {
        'accuracy': [],
        'precision': [],
        'recall': [],
        'f1': [],
        'auc': []
    }
    
    params = {
        'objective': 'binary',
        'metric': 'binary_logloss',
        'boosting_type': 'gbdt',
        'num_leaves': 31,
        'learning_rate': 0.05,
        'feature_fraction': 0.9,
        'bagging_fraction': 0.8,
        'bagging_freq': 5,
        'verbose': -1,
        'random_state': 42
    }
    
    fold = 1
    for train_idx, val_idx in tscv.split(X):
        X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
        y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]
        
        # Check class balance in validation set
        pos_rate = y_val.mean()
        
        train_data = lgb.Dataset(X_train, label=y_train)
        val_data = lgb.Dataset(X_val, label=y_val, reference=train_data)
        
        model = lgb.train(params, train_data, num_boost_round=1000, 
                          valid_sets=[val_data],
                          callbacks=[lgb.early_stopping(20, verbose=False)])
        
        y_pred_prob = model.predict(X_val)
        y_pred = (y_pred_prob > 0.5).astype(int)
        
        acc = accuracy_score(y_val, y_pred)
        prec = precision_score(y_val, y_pred, zero_division=0)
        rec = recall_score(y_val, y_pred, zero_division=0)
        f1 = f1_score(y_val, y_pred, zero_division=0)
        try:
            auc = roc_auc_score(y_val, y_pred_prob)
        except:
            auc = 0.5
            
        metrics['accuracy'].append(acc)
        metrics['precision'].append(prec)
        metrics['recall'].append(rec)
        metrics['f1'].append(f1)
        metrics['auc'].append(auc)
        
        print(f"Fold {fold}: Acc={acc:.4f}, Prec={prec:.4f}, Rec={rec:.4f}, F1={f1:.4f}, AUC={auc:.4f} (Pos Rate: {pos_rate:.2f})")
        fold += 1
        
    print("-" * 60)
    print(f"Average Accuracy:  {np.mean(metrics['accuracy']):.4f} ± {np.std(metrics['accuracy']):.4f}")
    print(f"Average Precision: {np.mean(metrics['precision']):.4f}")
    print(f"Average Recall:    {np.mean(metrics['recall']):.4f}")
    print(f"Average F1 Score:  {np.mean(metrics['f1']):.4f}")
    print(f"Average AUC:       {np.mean(metrics['auc']):.4f}")
    print("=" * 60)

def run_validation():
    print("Loading data...")
    match_df = load_match_level_data()
    
    # Define excluded columns (metadata + target + odds if any remain)
    exclude = ['date', 'Date', 'Div', 'Time', 'HomeTeam', 'AwayTeam', 
               'FTHG', 'FTAG', 'FTR', 'HTHG', 'HTAG', 'HTR',
               'home_team', 'away_team', 'home_score', 'away_score',
               'home_half_time_goals', 'away_half_time_goals',
               'home_shots', 'away_shots', 'home_shots_on_target', 'away_shots_on_target',
               'home_corners', 'away_corners', 'home_fouls', 'away_fouls',
               'home_yellow_cards', 'away_yellow_cards', 'home_red_cards', 'away_red_cards',
               'odds_home', 'odds_draw', 'odds_away', 'odds_over_2_5', 'odds_under_2_5',
               'odds_btts_yes', 'odds_btts_no',
               'total_goals', 'over_2_5', 'btts', 'year',
               'implied_prob_over', 'implied_prob_under', 'implied_prob_btts'] # Ensure these are excluded even if present
    
    # --- Validate Over/Under 2.5 ---
    df_ou = engineer_over_under_2_5_features(match_df)
    df_ou = df_ou[df_ou['over_2_5'].notna()]
    features_ou = [c for c in df_ou.columns if c not in exclude and df_ou[c].dtype in [np.float64, np.int64]]
    
    validate_model("Over/Under 2.5", df_ou, features_ou, 'over_2_5')
    
    # --- Validate BTTS ---
    # df_btts = engineer_btts_features(match_df)
    # df_btts = df_btts[df_btts['btts'].notna()]
    # features_btts = [c for c in df_btts.columns if c not in exclude and df_btts[c].dtype in [np.float64, np.int64]]
    
    # validate_model("BTTS", df_btts, features_btts, 'btts')

if __name__ == "__main__":
    run_validation()
