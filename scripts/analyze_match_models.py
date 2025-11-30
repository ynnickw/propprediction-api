import pandas as pd
import numpy as np
import lightgbm as lgb
import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config.settings import settings
from app.features.data_loader import load_match_level_data
from app.features.pipeline import engineer_over_under_2_5_features, engineer_btts_features

MODEL_DIR = settings.MODEL_DIR

def analyze_models():
    print("="*60)
    print("MATCH MODEL ANALYSIS")
    print("="*60)

    # 1. Load Data
    print("\nLoading match data...")
    match_df = load_match_level_data()
    
    # 2. Analyze Over/Under 2.5
    print("\n--- Over/Under 2.5 Analysis ---")
    df_ou = engineer_over_under_2_5_features(match_df)
    
    if 'over_2_5' in df_ou.columns:
        counts = df_ou['over_2_5'].value_counts(normalize=True)
        print(f"Class Balance (Over 2.5):")
        print(counts)
        baseline = counts.max()
        print(f"Baseline Accuracy (Majority Class): {baseline:.4f}")
    
    # Load Model
    model_path = os.path.join(MODEL_DIR, "lgbm_over_under_2.5.txt")
    if os.path.exists(model_path):
        model = lgb.Booster(model_file=model_path)
        print("\nFeature Importance (Top 10):")
        importance = pd.DataFrame({
            'feature': model.feature_name(),
            'importance': model.feature_importance()
        }).sort_values('importance', ascending=False).head(10)
        print(importance.to_string(index=False))
    else:
        print("Model file not found.")

    # 3. Analyze BTTS
    # print("\n--- BTTS Analysis ---")
    # df_btts = engineer_btts_features(match_df)
    
    # if 'btts' in df_btts.columns:
    #     counts = df_btts['btts'].value_counts(normalize=True)
    #     print(f"Class Balance (BTTS):")
    #     print(counts)
    #     baseline = counts.max()
    #     print(f"Baseline Accuracy (Majority Class): {baseline:.4f}")

    # # Load Model
    # model_path = os.path.join(MODEL_DIR, "lgbm_btts.txt")
    # if os.path.exists(model_path):
    #     model = lgb.Booster(model_file=model_path)
    #     print("\nFeature Importance (Top 10):")
    #     importance = pd.DataFrame({
    #         'feature': model.feature_name(),
    #         'importance': model.feature_importance()
    #     }).sort_values('importance', ascending=False).head(10)
    #     print(importance.to_string(index=False))
    # else:
    #     print("Model file not found.")

if __name__ == "__main__":
    analyze_models()
