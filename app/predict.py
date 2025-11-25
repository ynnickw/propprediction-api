import os
import pandas as pd
import numpy as np
import joblib
import lightgbm as lgb
import structlog
from datetime import datetime, timedelta
from scipy.stats import poisson

logger = structlog.get_logger()

# Constants
DATA_DIR = "data"
MODELS_DIR = "models"
HISTORY_FILE = os.path.join(DATA_DIR, "player_stats_history_enriched.csv")
OUTPUT_FILE = os.path.join(DATA_DIR, "predictions.csv")

def load_models(prop_type):
    """Load LightGBM and Poisson models for a specific prop type."""
    try:
        lgbm_path = os.path.join(MODELS_DIR, f"lgbm_{prop_type}.txt")
        poisson_path = os.path.join(MODELS_DIR, f"poisson_{prop_type}.joblib")
        
        if not os.path.exists(lgbm_path) or not os.path.exists(poisson_path):
            logger.warning(f"Models not found for {prop_type}")
            return None, None
            
        gbm = lgb.Booster(model_file=lgbm_path)
        poisson_pipeline = joblib.load(poisson_path)
        
        return gbm, poisson_pipeline
    except Exception as e:
        logger.error(f"Error loading models for {prop_type}: {e}")
        return None, None

def calculate_features_for_match(player_id, match_date, team, opponent, is_home, history_df):
    """
    Calculate features for a specific match using ONLY history prior to that match.
    """
    # Filter history to strictly BEFORE this match
    past_history = history_df[
        (history_df['player_id'] == player_id) & 
        (history_df['date'] < match_date)
    ].sort_values('date')
    
    if past_history.empty:
        return None

    # Get the most recent stats (last game played)
    last_stats = past_history.iloc[-1]
    
    # For opponent strength, look at opponent's games before this match
    opp_history = history_df[
        (history_df['opponent'] == opponent) & 
        (history_df['date'] < match_date)
    ].sort_values('date')
    
    opp_last_match = opp_history.iloc[-1] if not opp_history.empty else None
    
    features = {
        # Player form (from last available game)
        'shots_ema_5': last_stats.get('shots_ema_5', 0),
        'shots_last_5': last_stats.get('shots_last_5', 0),
        'shots_on_target_ema_5': last_stats.get('shots_on_target_ema_5', 0),
        'shots_on_target_last_5': last_stats.get('shots_on_target_last_5', 0),
        'goals_last_5': last_stats.get('goals_last_5', 0),
        'assists_last_5': last_stats.get('assists_last_5', 0),
        
        # Player characteristics
        'is_striker': 1 if last_stats.get('position') == 'F' else 0,
        'minutes_last_5': last_stats.get('minutes_last_5', 60),
        'rating_last_5': last_stats.get('rating_last_5', 6.5),
        
        # Match context
        'is_home': 1 if is_home else 0,
        
        # Team/Opponent Strength (Rolling)
        'team_shots_avg': last_stats.get('team_shots_avg', 12.0),
        'opp_conceded_shots_avg': opp_last_match['opp_conceded_shots_avg'] if opp_last_match is not None else 12.0,
        
        # External Data (Odds) - In a real scenario, these come from the Bookmaker for the UPCOMING match.
        # Here, we don't have them in the history for the 'next' game unless we look at the target row itself.
        # Since we are simulating predicting the 'target' row, we CAN look at the target row's odds (pre-match info).
        # But calculate_features is usually blind to the target row. 
        # We will pass odds in separately or handle them outside.
    }
    return features

def run_predictions():
    logger.info("Starting CSV-based prediction cycle...")
    
    if not os.path.exists(HISTORY_FILE):
        logger.error("History file not found.")
        return
    
    df = pd.read_csv(HISTORY_FILE)
    df['date'] = pd.to_datetime(df['date'])
    
    # --- Feature Engineering (Match Train Logic) ---
    # Calculate team shots and opponent shots for each match
    # Note: This assumes HS/AS columns exist in the enriched CSV (which they should)
    if 'HS' in df.columns and 'AS' in df.columns:
        df['team_shots'] = np.where(df['is_home'] == 1, df['HS'], df['AS'])
        df['opp_shots'] = np.where(df['is_home'] == 1, df['AS'], df['HS'])
        
        # Calculate rolling averages
        # We must group by team/opponent and shift(1) to avoid leakage (using current game stats)
        df = df.sort_values('date')
        df['team_shots_avg'] = df.groupby('team')['team_shots'].transform(lambda x: x.rolling(10, min_periods=1).mean().shift(1))
        df['opp_conceded_shots_avg'] = df.groupby('opponent')['opp_shots'].transform(lambda x: x.rolling(10, min_periods=1).mean().shift(1))
        
        # Fill NaNs for the first few games
        df['team_shots_avg'] = df['team_shots_avg'].fillna(12.0)
        df['opp_conceded_shots_avg'] = df['opp_conceded_shots_avg'].fillna(12.0)
    else:
        logger.warning("HS/AS columns missing. Using defaults for team strength.")
        df['team_shots_avg'] = 12.0
        df['opp_conceded_shots_avg'] = 12.0

    # 1. Identify "Upcoming" Matches
    # For this demo, we'll take the matches from the LAST available date in the dataset.
    last_date = df['date'].max()
    target_matches = df[df['date'] == last_date].copy()
    
    logger.info(f"Predicting for matches on {last_date.date()} ({len(target_matches)} player-matches found)")
    
    predictions = []
    
    # Load Models
    models = {}
    for prop in ['shots', 'shots_on_target', 'goals', 'assists']:
        models[prop] = load_models(prop)

    for idx, row in target_matches.iterrows():
        player_id = row['player_id']
        match_date = row['date']
        team = row['team']
        opponent = row['opponent']
        is_home = row['is_home']
        player_name = row['player_name']
        
        # Calculate Features (using only PAST data)
        features_dict = calculate_features_for_match(player_id, match_date, team, opponent, is_home, df)
        
        if not features_dict:
            continue
            
        # Add Pre-Match Odds (Available in the row itself)
        features_dict['B365H'] = row.get('B365H', 2.5)
        features_dict['B365D'] = row.get('B365D', 3.2)
        features_dict['B365A'] = row.get('B365A', 2.5)
        features_dict['implied_prob_home'] = row.get('implied_prob_home', 0.4)
        features_dict['implied_prob_away'] = row.get('implied_prob_away', 0.4)
        features_dict['is_favorite'] = row.get('is_favorite', 0)

        # Prepare X_pred
        X_pred = pd.DataFrame([features_dict])
        
        feature_cols = [
            'shots_ema_5', 'shots_last_5',
            'shots_on_target_ema_5', 'shots_on_target_last_5',
            'goals_last_5', 'assists_last_5',
            'is_striker', 'minutes_last_5', 
            'rating_last_5',
            'is_home', 
            'team_shots_avg', 'opp_conceded_shots_avg',
            'B365H', 'B365D', 'B365A'
        ]
        
        # Ensure cols exist
        for col in feature_cols:
            if col not in X_pred.columns:
                X_pred[col] = 0
        X_pred = X_pred[feature_cols]
        
        # Predict for each prop
        for prop_type, (gbm, poisson_pipeline) in models.items():
            if not gbm: continue
            
            try:
                pred_lgb = gbm.predict(X_pred, num_iteration=gbm.best_iteration)[0]
                pred_pois = poisson_pipeline.predict(X_pred)[0]
                pred_ensemble = (pred_lgb + pred_pois) / 2
                
                # Store Prediction
                predictions.append({
                    'date': match_date,
                    'player': player_name,
                    'team': team,
                    'opponent': opponent,
                    'prop': prop_type,
                    'prediction': round(pred_ensemble, 2),
                    'actual': row.get(prop_type, np.nan) # Actual result for comparison!
                })
            except Exception as e:
                logger.error(f"Error predicting {prop_type} for {player_name}: {e}")

    # Save Results
    pred_df = pd.DataFrame(predictions)
    if not pred_df.empty:
        pred_df.to_csv(OUTPUT_FILE, index=False)
        logger.info(f"Predictions saved to {OUTPUT_FILE}")
        print(pred_df.head(10))
    else:
        logger.warning("No predictions generated.")

if __name__ == "__main__":
    run_predictions()
