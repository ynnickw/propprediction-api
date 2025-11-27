"""
Feature engineering for match-level predictions.

This module handles:
- Loading match-level and player-level datasets
- Aggregating player statistics to team-level features
- Creating rolling window features
- Engineering interaction features for match predictions
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Callable
from datetime import datetime, date
import structlog
import os

logger = structlog.get_logger()

DATA_DIR = "data"


def load_match_level_data(years: List[int] = None) -> pd.DataFrame:
    """
    Load match-level datasets (D1_*.csv files).
    
    Args:
        years: List of years to load (e.g., [2020, 2021, 2022, 2023, 2024, 2025])
               If None, loads all available years
    
    Returns:
        DataFrame with match-level data
    """
    if years is None:
        years = [2020, 2021, 2022, 2023, 2024, 2025]
    
    dfs = []
    for year in years:
        file_path = os.path.join(DATA_DIR, f"D1_{year}.csv")
        if os.path.exists(file_path):
            logger.info(f"Loading match data from {file_path}")
            df = pd.read_csv(file_path)
            df['year'] = year
            dfs.append(df)
        else:
            logger.warning(f"Match data file not found: {file_path}")
    
    if not dfs:
        raise FileNotFoundError(f"No match-level data files found in {DATA_DIR}")
    
    combined = pd.concat(dfs, ignore_index=True)
    logger.info(f"Loaded {len(combined)} match records")
    return combined


def load_player_level_data() -> pd.DataFrame:
    """
    Load player-level dataset for aggregation.
    
    Returns:
        DataFrame with player-level statistics
    """
    file_path = os.path.join(DATA_DIR, "player_stats_history_enriched.csv")
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Player data file not found: {file_path}")
    
    logger.info(f"Loading player data from {file_path}")
    df = pd.read_csv(file_path)
    df['date'] = pd.to_datetime(df['date'])
    logger.info(f"Loaded {len(df)} player records")
    return df


def aggregate_player_stats_by_team(df: pd.DataFrame, match_date: date, team_name: str) -> Dict[str, float]:
    """
    Aggregate player statistics to team-level for a specific match date.
    
    Args:
        df: Player-level DataFrame
        match_date: Date of the match
        team_name: Team name to aggregate for
    
    Returns:
        Dictionary with aggregated team statistics
    """
    # Filter to team and date range (last N matches before match_date)
    team_df = df[(df['team'] == team_name) & (df['date'] < pd.Timestamp(match_date))]
    
    if len(team_df) == 0:
        logger.warning(f"No historical data found for team {team_name} before {match_date}")
        return {}
    
    # Aggregate by match date first
    match_stats = team_df.groupby('date').agg({
        'goals': 'sum',
        'shots': 'sum',
        'shots_on_target': 'sum',
        'assists': 'sum'
    }).reset_index()
    
    # Calculate rolling averages
    match_stats = match_stats.sort_values('date')
    
    stats = {
        'goals_scored_avg_last_5': match_stats['goals'].tail(5).mean() if len(match_stats) >= 5 else match_stats['goals'].mean(),
        'goals_scored_avg_last_10': match_stats['goals'].tail(10).mean() if len(match_stats) >= 10 else match_stats['goals'].mean(),
        'shots_avg_last_5': match_stats['shots'].tail(5).mean() if len(match_stats) >= 5 else match_stats['shots'].mean(),
        'shots_on_target_avg_last_5': match_stats['shots_on_target'].tail(5).mean() if len(match_stats) >= 5 else match_stats['shots_on_target'].mean(),
    }
    
    return stats


def create_rolling_window_features(df: pd.DataFrame, team_col: str, value_col: str, 
                                   window_sizes: List[int] = [5, 10]) -> pd.DataFrame:
    """
    Create rolling window features for team statistics.
    
    Args:
        df: DataFrame with team statistics
        team_col: Column name for team identifier
        value_col: Column name for value to calculate rolling average
        window_sizes: List of window sizes (e.g., [5, 10])
    
    Returns:
        DataFrame with rolling window features added
    """
    df = df.sort_values(['date', team_col])
    
    for window in window_sizes:
        col_name = f"{value_col}_avg_last_{window}"
        values = df.groupby(team_col)[value_col].transform(
            lambda x: x.rolling(window, min_periods=1).mean().shift(1)
        )
        df.loc[:, col_name] = values
    
    return df


def _validate_and_prepare_dataframe(df: pd.DataFrame, required_cols: List[str]) -> pd.DataFrame:
    """
    Common validation and preparation for feature engineering.
    
    Args:
        df: Input DataFrame
        required_cols: List of required column names
    
    Returns:
        Validated and prepared DataFrame
    """
    if df.empty:
        logger.warning("Empty DataFrame provided for feature engineering")
        return df
    
    df = df.copy()
    
    # Validate required columns
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        logger.error(f"Missing required columns: {missing_cols}")
        raise ValueError(f"Missing required columns: {missing_cols}")
    
    # Ensure date column exists
    if 'date' not in df.columns:
        logger.warning("Date column not found, using index for sorting")
        df['date'] = pd.Timestamp.now()
    
    df = df.sort_values('date')
    return df


def _add_rolling_averages(df: pd.DataFrame, team_col: str, value_col: str, 
                          prefix: str, window_sizes: List[int] = [5, 10]) -> pd.DataFrame:
    """
    Add rolling average features for a team statistic.
    
    Args:
        df: DataFrame
        team_col: Team identifier column
        value_col: Value column to calculate rolling average
        prefix: Prefix for feature names (e.g., 'home_goals')
        window_sizes: List of window sizes
    
    Returns:
        DataFrame with rolling average features added
    """
    # Use .loc to avoid pandas FutureWarning about chained assignment
    for window in window_sizes:
        feature_name = f'{prefix}_avg_last_{window}'
        values = df.groupby(team_col)[value_col].transform(
            lambda x: x.rolling(window, min_periods=1).mean().shift(1)
        )
        df.loc[:, feature_name] = values
    return df


def _add_expanding_average(df: pd.DataFrame, team_col: str, value_col: str, 
                          prefix: str, suffix: str = 'season') -> pd.DataFrame:
    """
    Add expanding (season) average feature.
    
    Args:
        df: DataFrame
        team_col: Team identifier column
        value_col: Value column to calculate expanding average
        prefix: Prefix for feature name
        suffix: Suffix for feature name (default: 'season')
    
    Returns:
        DataFrame with expanding average feature added
    """
    feature_name = f'{prefix}_avg_{suffix}'
    # Use .loc to avoid pandas FutureWarning about chained assignment
    values = df.groupby(team_col)[value_col].transform(
        lambda x: x.expanding().mean().shift(1)
    )
    df.loc[:, feature_name] = values
    return df


def _add_binary_rate_features(df: pd.DataFrame, team_col: str, value_col: str, 
                              prefix: str, condition_func) -> pd.DataFrame:
    """
    Add binary rate features (e.g., scoring rate, conceding rate).
    
    Args:
        df: DataFrame
        team_col: Team identifier column
        value_col: Value column to evaluate condition
        prefix: Prefix for feature names
        condition_func: Function to apply (e.g., lambda x: x > 0)
    
    Returns:
        DataFrame with binary rate features added
    """
    # Season rate (expanding)
    # Use .loc to avoid pandas FutureWarning about chained assignment
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


def _add_team_statistics_for_both_sides(df: pd.DataFrame, stat_configs: List[Dict]) -> pd.DataFrame:
    """
    Add team statistics for both Home and Away teams.
    
    Args:
        df: DataFrame
        stat_configs: List of dicts with keys:
            - 'value_col': Column name for the statistic
            - 'prefix_template': Template for feature prefix (e.g., '{team_type}_goals')
            - 'windows': List of window sizes for rolling averages
            - 'include_season': Whether to include season average
    
    Returns:
        DataFrame with team statistics added
    """
    for team_type in ['Home', 'Away']:
        team_col = f'{team_type}Team'
        
        for config in stat_configs:
            value_col = config['value_col']
            prefix_template = config['prefix_template']
            prefix = prefix_template.format(team_type=team_type.lower())
            
            # Rolling averages
            if 'windows' in config:
                df = _add_rolling_averages(df, team_col, value_col, prefix, config['windows'])
            
            # Season average
            if config.get('include_season', False):
                df = _add_expanding_average(df, team_col, value_col, prefix)
    
    return df


def merge_match_and_player_data(match_df: pd.DataFrame, player_df: pd.DataFrame) -> pd.DataFrame:
    """
    Merge match-level and player-level data for comprehensive feature engineering.
    
    Args:
        match_df: Match-level DataFrame
        player_df: Player-level DataFrame
    
    Returns:
        Merged DataFrame
    """
    logger.info("Merging match and player data")
    
    # Aggregate player stats by team and date
    player_agg = player_df.groupby(['team', 'date']).agg({
        'goals': 'sum',
        'shots': 'sum',
        'shots_on_target': 'sum',
        'assists': 'sum'
    }).reset_index()
    player_agg.columns = ['team', 'date', 'team_goals', 'team_shots', 'team_shots_on_target', 'team_assists']
    
    # Merge with match data (home team)
    match_df = pd.merge(
        match_df, 
        player_agg,
        left_on=['HomeTeam', 'date'],
        right_on=['team', 'date'],
        how='left',
        suffixes=('', '_home')
    )
    
    # Merge with match data (away team)
    match_df = pd.merge(
        match_df,
        player_agg,
        left_on=['AwayTeam', 'date'],
        right_on=['team', 'date'],
        how='left',
        suffixes=('', '_away')
    )
    
    return match_df


def prepare_match_features_for_training(match_df: pd.DataFrame, 
                                        player_df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    """
    Prepare features for match-level model training.
    
    Args:
        match_df: Match-level DataFrame
        player_df: Optional player-level DataFrame for additional features
    
    Returns:
        DataFrame with engineered features ready for training
    """
    logger.info("Preparing match features for training")
    
    # Parse date column
    if 'Date' in match_df.columns:
        match_df['date'] = pd.to_datetime(match_df['Date'], format='%d/%m/%Y', errors='coerce')
    elif 'date' not in match_df.columns:
        raise ValueError("Date column not found in match DataFrame")
    
    # Sort by date for time-based splitting
    match_df = match_df.sort_values('date')
    
    # Create target variables
    if 'FTHG' in match_df.columns and 'FTAG' in match_df.columns:
        match_df['total_goals'] = match_df['FTHG'] + match_df['FTAG']
        match_df['over_2_5'] = (match_df['total_goals'] > 2.5).astype(int)
        match_df['btts'] = ((match_df['FTHG'] > 0) & (match_df['FTAG'] > 0)).astype(int)
    
    # TODO: Add feature engineering logic here
    # This will be expanded in subsequent tasks
    
    return match_df


def engineer_over_under_2_5_features(match_df: pd.DataFrame) -> pd.DataFrame:
    """
    Engineer features specifically for Over/Under 2.5 goals prediction.
    
    Args:
        match_df: Match-level DataFrame with basic columns
    
    Returns:
        DataFrame with engineered features
    """
    logger.info("Engineering Over/Under 2.5 features")
    
    # Validate and prepare
    df = _validate_and_prepare_dataframe(match_df, ['HomeTeam', 'AwayTeam'])
    if df.empty:
        return df
    
    # Create target variables if not already present
    if 'over_2_5' not in df.columns:
        if 'FTHG' in df.columns and 'FTAG' in df.columns:
            df.loc[:, 'total_goals'] = df['FTHG'] + df['FTAG']
            df.loc[:, 'over_2_5'] = (df['total_goals'] > 2.5).astype(int)
            df.loc[:, 'btts'] = ((df['FTHG'] > 0) & (df['FTAG'] > 0)).astype(int)
        else:
            logger.warning("FTHG/FTAG columns not found, cannot create over_2_5 target")
            df.loc[:, 'over_2_5'] = np.nan
    
    # Team goals scored statistics
    goals_configs = [
        {'value_col': 'FTHG', 'prefix_template': '{team_type}_goals', 'windows': [5, 10], 'include_season': True},
        {'value_col': 'FTAG', 'prefix_template': '{team_type}_goals', 'windows': [5, 10], 'include_season': True}
    ]
    
    # Add goals scored features for home team
    df = _add_rolling_averages(df, 'HomeTeam', 'FTHG', 'home_goals', [5, 10])
    df = _add_expanding_average(df, 'HomeTeam', 'FTHG', 'home_goals')
    
    # Add goals scored features for away team
    df = _add_rolling_averages(df, 'AwayTeam', 'FTAG', 'away_goals', [5, 10])
    df = _add_expanding_average(df, 'AwayTeam', 'FTAG', 'away_goals')
    
    # Goals conceded (opponent perspective)
    df = _add_rolling_averages(df, 'HomeTeam', 'FTAG', 'home_goals_conceded', [5, 10])
    df = _add_expanding_average(df, 'HomeTeam', 'FTAG', 'home_goals_conceded')
    
    df = _add_rolling_averages(df, 'AwayTeam', 'FTHG', 'away_goals_conceded', [5, 10])
    df = _add_expanding_average(df, 'AwayTeam', 'FTHG', 'away_goals_conceded')
    
    # Shots statistics (if available)
    for team_type in ['Home', 'Away']:
        team_col = f'{team_type}Team'
        shots_col = f'{team_type[0]}S'
        shots_on_target_col = f'{team_type[0]}ST'
        
        if shots_col in df.columns:
            df = _add_rolling_averages(df, team_col, shots_col, f'{team_type.lower()}_shots', [5])
        
        if shots_on_target_col in df.columns:
            df = _add_rolling_averages(df, team_col, shots_on_target_col, f'{team_type.lower()}_shots_on_target', [5])
    
    # Home/Away splits
    for team_type in ['Home', 'Away']:
        team_col = f'{team_type}Team'
        goals_col = f'FT{team_type[0]}G'
        is_home = 1 if team_type == 'Home' else 0
        
        # Filter by home/away
        home_away_df = df[df.apply(lambda row: (row['HomeTeam'] == row[team_col] and is_home == 1) or 
                                   (row['AwayTeam'] == row[team_col] and is_home == 0), axis=1)]
        
        if len(home_away_df) > 0:
            feature_name = f'{team_type.lower()}_goals_avg_{"home" if is_home else "away"}'
            values = df.groupby(team_col)[goals_col].transform(
                lambda x: x.rolling(10, min_periods=1).mean().shift(1)
            )
            df.loc[:, feature_name] = values
    
    # Head-to-head history
    h2h_values = df.apply(
        lambda row: calculate_h2h_total_goals_avg(df, row['HomeTeam'], row['AwayTeam'], row['date']), 
        axis=1
    )
    df.loc[:, 'h2h_total_goals_avg'] = h2h_values
    
    # Interaction features
    df.loc[:, 'combined_offensive_strength'] = (
        df['home_goals_avg_season'].fillna(0) + df['away_goals_avg_season'].fillna(0)
    )
    df.loc[:, 'combined_defensive_weakness'] = (
        df['home_goals_conceded_avg_season'].fillna(0) + df['away_goals_conceded_avg_season'].fillna(0)
    )
    df.loc[:, 'home_offense_vs_away_defense'] = (
        df['home_goals_avg_season'].fillna(0) - df['away_goals_conceded_avg_season'].fillna(0)
    )
    df.loc[:, 'away_offense_vs_home_defense'] = (
        df['away_goals_avg_season'].fillna(0) - df['home_goals_conceded_avg_season'].fillna(0)
    )
    
    # Bookmaker odds features
    if 'B365>2.5' in df.columns:
        df.loc[:, 'odds_over_2_5'] = df['B365>2.5']
        df.loc[:, 'odds_under_2_5'] = df['B365<2.5']
        df.loc[:, 'implied_prob_over'] = 1.0 / df['odds_over_2_5'].fillna(2.0)
        df.loc[:, 'implied_prob_under'] = 1.0 / df['odds_under_2_5'].fillna(2.0)
    
    # Fill NaN values with defaults
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    df.loc[:, numeric_cols] = df[numeric_cols].fillna(0)
    
    return df


def calculate_h2h_total_goals_avg(df: pd.DataFrame, home_team: str, away_team: str, 
                                  current_date: pd.Timestamp, n_matches: int = 5) -> float:
    """
    Calculate average total goals in head-to-head meetings.
    
    Args:
        df: Match DataFrame
        home_team: Home team name
        away_team: Away team name
        current_date: Current match date
        n_matches: Number of previous meetings to consider
    
    Returns:
        Average total goals in last n_matches meetings
    """
    # Find previous meetings between these teams
    h2h_matches = df[
        ((df['HomeTeam'] == home_team) & (df['AwayTeam'] == away_team)) |
        ((df['HomeTeam'] == away_team) & (df['AwayTeam'] == home_team))
    ]
    h2h_matches = h2h_matches[h2h_matches['date'] < current_date].tail(n_matches)
    
    if len(h2h_matches) == 0:
        return 0.0
    
    if 'FTHG' in h2h_matches.columns and 'FTAG' in h2h_matches.columns:
        total_goals = (h2h_matches['FTHG'] + h2h_matches['FTAG']).mean()
        return float(total_goals)
    
    return 0.0


def engineer_btts_features(match_df: pd.DataFrame) -> pd.DataFrame:
    """
    Engineer features specifically for Both Teams To Score (BTTS) prediction.
    
    Args:
        match_df: Match-level DataFrame with basic columns
    
    Returns:
        DataFrame with engineered features for BTTS
    """
    logger.info("Engineering BTTS features")
    
    # Validate and prepare
    df = _validate_and_prepare_dataframe(match_df, ['HomeTeam', 'AwayTeam'])
    if df.empty:
        return df
    
    # Create target variables if not already present
    if 'btts' not in df.columns:
        if 'FTHG' in df.columns and 'FTAG' in df.columns:
            if 'total_goals' not in df.columns:
                df.loc[:, 'total_goals'] = df['FTHG'] + df['FTAG']
            df.loc[:, 'btts'] = ((df['FTHG'] > 0) & (df['FTAG'] > 0)).astype(int)
            if 'over_2_5' not in df.columns:
                df.loc[:, 'over_2_5'] = (df['total_goals'] > 2.5).astype(int)
        else:
            logger.warning("FTHG/FTAG columns not found, cannot create btts target")
            df.loc[:, 'btts'] = np.nan
    
    # Team scoring consistency features
    for team_type in ['Home', 'Away']:
        team_col = f'{team_type}Team'
        goals_col = f'FT{team_type[0]}G'  # FTHG or FTAG
        opponent_goals_col = f'FT{"A" if team_type == "Home" else "H"}G'  # Opponent goals
        
        # Scoring rate (percentage of matches where team scored)
        df = _add_binary_rate_features(df, team_col, goals_col, f'{team_type.lower()}_scoring', lambda x: x > 0)
        
        # Average goals scored
        df = _add_rolling_averages(df, team_col, goals_col, f'{team_type.lower()}_goals', [5])
        df = _add_expanding_average(df, team_col, goals_col, f'{team_type.lower()}_goals')
        
        # Scoreless frequency (matches with 0 goals)
        scoreless_values = df.groupby(team_col)[goals_col].transform(
            lambda x: (x == 0).expanding().mean().shift(1)
        )
        df.loc[:, f'{team_type.lower()}_scoreless_rate'] = scoreless_values
        
        # Conceding rate (percentage of matches where team conceded)
        df = _add_binary_rate_features(df, team_col, opponent_goals_col, f'{team_type.lower()}_conceding', lambda x: x > 0)
        
        # Clean sheet frequency (matches with 0 goals conceded)
        clean_sheet_values = df.groupby(team_col)[opponent_goals_col].transform(
            lambda x: (x == 0).expanding().mean().shift(1)
        )
        df.loc[:, f'{team_type.lower()}_clean_sheet_rate'] = clean_sheet_values
    
    # Head-to-head BTTS history
    h2h_btts_values = df.apply(
        lambda row: calculate_h2h_btts_rate(df, row['HomeTeam'], row['AwayTeam'], row['date']),
        axis=1
    )
    df.loc[:, 'h2h_btts_rate'] = h2h_btts_values
    
    # Interaction features
    df.loc[:, 'combined_scoring_probability'] = (
        df['home_scoring_rate_season'].fillna(0) * df['away_scoring_rate_season'].fillna(0)
    )
    df.loc[:, 'defensive_weakness_indicator'] = (
        df['home_conceding_rate_season'].fillna(0) * df['away_conceding_rate_season'].fillna(0)
    )
    df.loc[:, 'home_scoring_vs_away_conceding'] = (
        df['home_scoring_rate_season'].fillna(0) - df['away_conceding_rate_season'].fillna(0)
    )
    df.loc[:, 'away_scoring_vs_home_conceding'] = (
        df['away_scoring_rate_season'].fillna(0) - df['home_conceding_rate_season'].fillna(0)
    )
    
    # Fill NaN values with defaults
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    df.loc[:, numeric_cols] = df[numeric_cols].fillna(0)
    
    return df


def calculate_h2h_btts_rate(df: pd.DataFrame, home_team: str, away_team: str,
                            current_date: pd.Timestamp, n_matches: int = 5) -> float:
    """
    Calculate BTTS rate in head-to-head meetings.
    
    Args:
        df: Match DataFrame
        home_team: Home team name
        away_team: Away team name
        current_date: Current match date
        n_matches: Number of previous meetings to consider
    
    Returns:
        BTTS rate (0.0 to 1.0) in last n_matches meetings
    """
    # Find previous meetings between these teams
    h2h_matches = df[
        ((df['HomeTeam'] == home_team) & (df['AwayTeam'] == away_team)) |
        ((df['HomeTeam'] == away_team) & (df['AwayTeam'] == home_team))
    ]
    h2h_matches = h2h_matches[h2h_matches['date'] < current_date].tail(n_matches)
    
    if len(h2h_matches) == 0:
        return 0.0
    
    if 'FTHG' in h2h_matches.columns and 'FTAG' in h2h_matches.columns:
        btts_count = ((h2h_matches['FTHG'] > 0) & (h2h_matches['FTAG'] > 0)).sum()
        btts_rate = btts_count / len(h2h_matches)
        return float(btts_rate)
    
    return 0.0

