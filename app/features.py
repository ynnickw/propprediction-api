import pandas as pd
import numpy as np
from typing import List, Dict, Optional
from .models import HistoricalStat, Match, Player

def calculate_rolling_stats(stats: List[HistoricalStat]) -> Dict[str, float]:
    """
    Calculate rolling averages and EMAs for player stats.
    Returns a dictionary of features matching the training logic.
    """
    if not stats:
        return {}
    
    # Sort by date (oldest first)
    sorted_stats = sorted(stats, key=lambda x: x.match_date)
    
    # Convert to DataFrame
    data = []
    for s in sorted_stats:
        row = {
            'shots': s.shots,
            'shots_on_target': s.shots_on_target,
            'goals': getattr(s, 'goals', 0),
            'assists': s.assists,
            'minutes': s.minutes_played,
            'rating': getattr(s, 'rating', 6.5) # Default if missing
        }
        data.append(row)
        
    df = pd.DataFrame(data)
    if df.empty:
        return {}
        
    features = {}
    
    # Columns to process
    cols = ['shots', 'shots_on_target', 'goals', 'assists', 'minutes', 'rating']
    
    for col in cols:
        if col not in df.columns:
            features[f'{col}_last_5'] = 0
            features[f'{col}_ema_5'] = 0
            continue
            
        # Rolling Mean (Last 5) - Simple Moving Average
        features[f'{col}_last_5'] = df[col].tail(5).mean()
        
        # EMA (Span 5) - Exponential Moving Average
        # We calculate EMA for the whole series and take the last one
        ema = df[col].ewm(span=5, adjust=False).mean()
        features[f'{col}_ema_5'] = ema.iloc[-1]
        
    return features

def prepare_features(player: Player, match: Match, historical_stats: List[HistoricalStat], 
                     team_stats: Optional[Dict] = None, odds: Optional[Dict] = None) -> pd.DataFrame:
    """
    Prepare features for a single prediction instance.
    
    Args:
        player: The Player object.
        match: The Match object (upcoming match).
        historical_stats: List of HistoricalStat objects for the player.
        team_stats: Dict containing 'team_shots_avg' and 'opp_conceded_shots_avg'.
        odds: Dict containing 'B365H', 'B365D', 'B365A'.
    """
    
    # 1. Player Stats (Rolling & EMA)
    player_features = calculate_rolling_stats(historical_stats)
    
    # 2. Defaults if missing
    if not team_stats:
        team_stats = {'team_shots_avg': 12.0, 'opp_conceded_shots_avg': 12.0}
    if not odds:
        odds = {'B365H': 2.5, 'B365D': 3.2, 'B365A': 2.5}
        
    # 3. Construct Feature Dictionary
    # MUST MATCH train.py features list EXACTLY
    features = {
        # Player Form
        'shots_ema_5': player_features.get('shots_ema_5', 0),
        'shots_last_5': player_features.get('shots_last_5', 0),
        'shots_on_target_ema_5': player_features.get('shots_on_target_ema_5', 0),
        'shots_on_target_last_5': player_features.get('shots_on_target_last_5', 0),
        'goals_last_5': player_features.get('goals_last_5', 0),
        'assists_last_5': player_features.get('assists_last_5', 0),
        
        # Player Characteristics
        'is_striker': 1 if player.position == 'F' else 0,
        'minutes_last_5': player_features.get('minutes_last_5', 60),
        'rating_last_5': player_features.get('rating_last_5', 6.5),
        
        # Match Context
        'is_home': 1 if player.team == match.home_team else 0,
        
        # Team Strength
        'team_shots_avg': team_stats.get('team_shots_avg', 12.0),
        'opp_conceded_shots_avg': team_stats.get('opp_conceded_shots_avg', 12.0),
        
        # Odds
        'B365H': odds.get('B365H', 2.5),
        'B365D': odds.get('B365D', 3.2),
        'B365A': odds.get('B365A', 2.5),
        
        # Extra features used in training but maybe not critical or can be defaulted
        'implied_prob_home': 1/odds.get('B365H', 2.5),
        'implied_prob_away': 1/odds.get('B365A', 2.5),
        'is_favorite': 1 if odds.get('B365H', 2.5) < odds.get('B365A', 2.5) and (1 if player.team == match.home_team else 0) else 0
    }
    
    # Return as DataFrame (1 row)
    return pd.DataFrame([features])
