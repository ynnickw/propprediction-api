import pandas as pd
import numpy as np
from typing import List, Dict
from .models import HistoricalStat, Match, Player

def calculate_rolling_averages(stats: List[HistoricalStat], window: int = 5) -> Dict[str, float]:
    """Calculate rolling averages for player stats."""
    if not stats:
        return {}
    
    df = pd.DataFrame([s.__dict__ for s in stats])
    if df.empty:
        return {}
        
    cols = ['shots', 'shots_on_target', 'assists', 'passes', 'tackles', 'cards']
    rolling_avg = df[cols].tail(window).mean().to_dict()
    return rolling_avg

def prepare_features(player: Player, match: Match, historical_stats: List[HistoricalStat]) -> pd.DataFrame:
    """Prepare features for a single prediction instance."""
    
    rolling_5 = calculate_rolling_averages(historical_stats, window=5)
    rolling_10 = calculate_rolling_averages(historical_stats, window=10)
    
    # Aligning with train.py feature schema
    features = {
        'is_home': 1 if player.team == match.home_team else 0,
        'minutes': 90, # Assumption for now
        'rest_days': 7, # Assumption
        'shots_ema_5': rolling_5.get('shots', 0),
        'shots_ema_10': rolling_10.get('shots', 0),
        'shots_on_target_ema_5': rolling_5.get('shots_on_target', 0),
        'shots_on_target_ema_10': rolling_10.get('shots_on_target', 0),
        'opp_conceded_shots': 10, # Placeholder average
        'opp_conceded_shots_on_target': 4 # Placeholder average
    }
    
    return pd.DataFrame([features])
