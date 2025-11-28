"""
Match prediction logic and edge calculation.

This module handles:
- Generating predictions for upcoming matches
- Calculating edge percentages
- Filtering picks by minimum edge threshold
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import structlog
import os

logger = structlog.get_logger()

MODEL_DIR = "models"


def load_match_models(prediction_type: str) -> Dict:
    """
    Load trained models for match predictions.
    
    Args:
        prediction_type: 'over_under_2.5' or 'btts'
    
    Returns:
        Dictionary with loaded models
    """
    models = {}
    
    # Load LightGBM model
    lgb_path = os.path.join(MODEL_DIR, f"lgbm_{prediction_type}.txt")
    if os.path.exists(lgb_path):
        import lightgbm as lgb
        models['lightgbm'] = lgb.Booster(model_file=lgb_path)
    
    # Load Poisson model
    poisson_path = os.path.join(MODEL_DIR, f"poisson_{prediction_type}.joblib")
    if os.path.exists(poisson_path):
        models['poisson'] = joblib.load(poisson_path)
    
    if not models:
        raise FileNotFoundError(f"No models found for {prediction_type}")
    
    return models


def predict_match_outcome(features: pd.DataFrame, prediction_type: str) -> Dict:
    """
    Generate prediction for a match using ensemble models.
    
    Args:
        features: DataFrame with match features (single row)
        prediction_type: 'over_under_2.5' or 'btts'
    
    Returns:
        Dictionary with prediction results
    """
    from .model import predict_match_outcome as model_predict
    
    return model_predict(features, prediction_type)


def calculate_edge(model_prob: float, bookmaker_odds: float) -> Tuple[float, float]:
    """
    Calculate edge percentage from model probability and bookmaker odds.
    
    Args:
        model_prob: Model's predicted probability
        bookmaker_odds: Bookmaker's odds
    
    Returns:
        Tuple of (bookmaker_implied_prob, edge_percent)
    """
    if bookmaker_odds is None or pd.isna(bookmaker_odds):
        logger.warning("Bookmaker odds are None or NaN, cannot calculate edge")
        return 0.0, 0.0
    
    if bookmaker_odds <= 1.0:
        logger.warning(f"Invalid bookmaker odds: {bookmaker_odds} (must be > 1.0)")
        return 0.0, 0.0
    
    if model_prob is None or pd.isna(model_prob) or model_prob < 0 or model_prob > 1:
        logger.warning(f"Invalid model probability: {model_prob} (must be between 0 and 1)")
        return 0.0, 0.0
    
    try:
        bookmaker_prob = 1.0 / bookmaker_odds
        edge_percent = (model_prob - bookmaker_prob) * 100
        return bookmaker_prob, edge_percent
    except Exception as e:
        logger.error(f"Error calculating edge: {e}")
        return 0.0, 0.0


def filter_picks_by_edge(predictions: List[Dict], min_edge: float = 8.0) -> List[Dict]:
    """
    Filter predictions by minimum edge threshold.
    
    Args:
        predictions: List of prediction dictionaries
        min_edge: Minimum edge percentage (default 8%)
    
    Returns:
        Filtered list of predictions with edge >= min_edge
    """
    filtered = [p for p in predictions if p.get('edge_percent', 0) >= min_edge]
    logger.info(f"Filtered {len(filtered)} picks from {len(predictions)} predictions (min_edge={min_edge}%)")
    return filtered


def prepare_match_features_for_prediction(match, historical_matches_df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    """
    Prepare features for a single match prediction from database Match object.
    
    Args:
        match: Match database object
        historical_matches_df: Optional DataFrame with historical match data for feature engineering
    
    Returns:
        DataFrame with features ready for model prediction
    """
    from .match_features import engineer_over_under_2_5_features, engineer_btts_features
    
    # Create a minimal DataFrame with match info
    # Create a minimal DataFrame with match info
    match_data = {
        'date': match.start_time if match.start_time else datetime.now(),
        'home_team': match.home_team,
        'away_team': match.away_team,
        'home_score': 0,  # Placeholder for upcoming match
        'away_score': 0,  # Placeholder for upcoming match
        'home_shots': 0,
        'away_shots': 0,
        'home_shots_on_target': 0,
        'away_shots_on_target': 0,
        'odds_over_2_5': match.odds_over_2_5 if match.odds_over_2_5 else 2.0,
        'odds_under_2_5': match.odds_under_2_5 if match.odds_under_2_5 else 2.0,
        'odds_btts_yes': match.odds_btts_yes if match.odds_btts_yes else 2.0,
        'odds_btts_no': match.odds_btts_no if match.odds_btts_no else 2.0
    }
    
    match_df = pd.DataFrame([match_data])
    match_df = pd.DataFrame([match_data])
    # date is already datetime in the dict
    
    # If historical data available, merge for better features
    if historical_matches_df is not None and len(historical_matches_df) > 0:
        # Append current match to historical data for feature engineering
        combined_df = pd.concat([historical_matches_df, match_df], ignore_index=True)
        
        # Engineer features (this will use historical context)
        df_over_under = engineer_over_under_2_5_features(combined_df)
        df_btts = engineer_btts_features(combined_df)
        
        # Get features for the specific match (it might not be the last row due to sorting)
        # We use the match date and teams to identify the row
        mask = (
            (df_over_under['date'] == match_data['date']) & 
            (df_over_under['home_team'] == match_data['home_team']) & 
            (df_over_under['away_team'] == match_data['away_team'])
        )
        
        if mask.any():
            features_over_under = df_over_under[mask].head(1)
            features_btts = df_btts[mask].head(1)
        else:
            # Fallback (should not happen)
            logger.warning("Could not find match row after feature engineering, using last row")
            features_over_under = df_over_under.iloc[[-1]]
            features_btts = df_btts.iloc[[-1]]
        
        return features_over_under, features_btts
    else:
        # Fallback: minimal features without historical context
        logger.warning(f"No historical data available for match {match.home_team} vs {match.away_team}")
        return match_df, match_df

