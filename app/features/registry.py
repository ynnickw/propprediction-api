import pandas as pd
import numpy as np
from typing import List, Dict, Callable
import structlog

logger = structlog.get_logger()

def create_rolling_window_features(df: pd.DataFrame, team_col: str, value_col: str, 
                                   window_sizes: List[int] = [5, 10]) -> pd.DataFrame:
    """Create rolling window features for team statistics."""
    df = df.sort_values(['date', team_col])
    
    for window in window_sizes:
        col_name = f"{value_col}_avg_last_{window}"
        values = df.groupby(team_col)[value_col].transform(
            lambda x: x.rolling(window, min_periods=1).mean().shift(1)
        )
        df.loc[:, col_name] = values
    
    return df

def add_rolling_averages(df: pd.DataFrame, team_col: str, value_col: str, 
                          prefix: str, window_sizes: List[int] = [5, 10]) -> pd.DataFrame:
    """Add rolling average features for a team statistic."""
    for window in window_sizes:
        feature_name = f'{prefix}_avg_last_{window}'
        values = df.groupby(team_col)[value_col].transform(
            lambda x: x.rolling(window, min_periods=1).mean().shift(1)
        )
        df.loc[:, feature_name] = values
    return df

def add_expanding_average(df: pd.DataFrame, team_col: str, value_col: str, 
                          prefix: str, suffix: str = 'season') -> pd.DataFrame:
    """Add expanding (season) average feature."""
    feature_name = f'{prefix}_avg_{suffix}'
    values = df.groupby(team_col)[value_col].transform(
        lambda x: x.expanding().mean().shift(1)
    )
    df.loc[:, feature_name] = values
    return df

def add_binary_rate_features(df: pd.DataFrame, team_col: str, value_col: str, 
                              prefix: str, condition_func: Callable) -> pd.DataFrame:
    """Add binary rate features (e.g., scoring rate, conceding rate)."""
    # Season rate (expanding)
    season_rate = df.groupby(team_col)[value_col].transform(
        lambda x: condition_func(x).expanding().mean().shift(1)
    )
    df.loc[:, f'{prefix}_rate_season'] = season_rate
    
    # Last 5 matches rate (rolling)
    last_5_rate = df.groupby(team_col)[value_col].transform(
        lambda x: condition_func(x).rolling(5, min_periods=1).mean().shift(1)
    )
    df.loc[:, f'{prefix}_rate_last_5'] = last_5_rate
    
    return df

def calculate_h2h_total_goals_avg(df: pd.DataFrame, home_team: str, away_team: str, 
                                  current_date: pd.Timestamp, n_matches: int = 5) -> float:
    """Calculate average total goals in head-to-head meetings."""
    h2h_matches = df[
        ((df['home_team'] == home_team) & (df['away_team'] == away_team)) |
        ((df['home_team'] == away_team) & (df['away_team'] == home_team))
    ]
    h2h_matches = h2h_matches[h2h_matches['date'] < current_date].tail(n_matches)
    
    if len(h2h_matches) == 0:
        return 0.0
    
    if 'home_score' in h2h_matches.columns and 'away_score' in h2h_matches.columns:
        total_goals = (h2h_matches['home_score'] + h2h_matches['away_score']).mean()
        return float(total_goals)
    
    return 0.0

def calculate_h2h_btts_rate(df: pd.DataFrame, home_team: str, away_team: str,
                            current_date: pd.Timestamp, n_matches: int = 5) -> float:
    """Calculate BTTS rate in head-to-head meetings."""
    h2h_matches = df[
        ((df['home_team'] == home_team) & (df['away_team'] == away_team)) |
        ((df['home_team'] == away_team) & (df['away_team'] == home_team))
    ]
    h2h_matches = h2h_matches[h2h_matches['date'] < current_date].tail(n_matches)
    
    if len(h2h_matches) == 0:
        return 0.0
    
    if 'home_score' in h2h_matches.columns and 'away_score' in h2h_matches.columns:
        btts_count = ((h2h_matches['home_score'] > 0) & (h2h_matches['away_score'] > 0)).sum()
        btts_rate = btts_count / len(h2h_matches)
        return float(btts_rate)
    
    return 0.0
