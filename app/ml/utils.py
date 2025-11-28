import pandas as pd
from typing import Tuple, List, Dict
import structlog

logger = structlog.get_logger()

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
    """Filter predictions by minimum edge threshold."""
    filtered = [p for p in predictions if p.get('edge_percent', 0) >= min_edge]
    logger.info(f"Filtered {len(filtered)} picks from {len(predictions)} predictions (min_edge={min_edge}%)")
    return filtered
