import pandas as pd
import numpy as np
from typing import List, Optional
import structlog
from .registry import (
    add_rolling_averages, 
    add_expanding_average, 
    add_binary_rate_features,
    calculate_h2h_total_goals_avg,
    calculate_h2h_btts_rate
)

logger = structlog.get_logger()

def validate_and_prepare_dataframe(df: pd.DataFrame, required_cols: List[str]) -> pd.DataFrame:
    """Common validation and preparation for feature engineering."""
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

def engineer_over_under_2_5_features(match_df: pd.DataFrame) -> pd.DataFrame:
    """Engineer features specifically for Over/Under 2.5 goals prediction."""
    logger.info("Engineering Over/Under 2.5 features")
    
    # Validate and prepare
    df = validate_and_prepare_dataframe(match_df, ['home_team', 'away_team'])
    if df.empty:
        return df
    
    # Create target variables if not already present
    if 'over_2_5' not in df.columns:
        if 'home_score' in df.columns and 'away_score' in df.columns:
            df.loc[:, 'total_goals'] = df['home_score'] + df['away_score']
            df.loc[:, 'over_2_5'] = (df['total_goals'] > 2.5).astype(int)
            df.loc[:, 'btts'] = ((df['home_score'] > 0) & (df['away_score'] > 0)).astype(int)
        else:
            logger.warning("home_score/away_score columns not found, cannot create over_2_5 target")
            df.loc[:, 'over_2_5'] = np.nan
    
    # Team goals scored statistics
    df = add_rolling_averages(df, 'home_team', 'home_score', 'home_goals', [5, 10])
    df = add_expanding_average(df, 'home_team', 'home_score', 'home_goals')
    
    df = add_rolling_averages(df, 'away_team', 'away_score', 'away_goals', [5, 10])
    df = add_expanding_average(df, 'away_team', 'away_score', 'away_goals')
    
    # Goals conceded (opponent perspective)
    df = add_rolling_averages(df, 'home_team', 'away_score', 'home_goals_conceded', [5, 10])
    df = add_expanding_average(df, 'home_team', 'away_score', 'home_goals_conceded')
    
    df = add_rolling_averages(df, 'away_team', 'home_score', 'away_goals_conceded', [5, 10])
    df = add_expanding_average(df, 'away_team', 'home_score', 'away_goals_conceded')
    
    # Shots statistics (if available)
    for team_type in ['home', 'away']:
        team_col = f'{team_type}_team'
        shots_col = f'{team_type}_shots'
        shots_on_target_col = f'{team_type}_shots_on_target'
        
        if shots_col in df.columns:
            df = add_rolling_averages(df, team_col, shots_col, f'{team_type}_shots', [5])
        
        if shots_on_target_col in df.columns:
            df = add_rolling_averages(df, team_col, shots_on_target_col, f'{team_type}_shots_on_target', [5])
    
    # Home/Away splits
    for team_type in ['home', 'away']:
        team_col = f'{team_type}_team'
        goals_col = f'{team_type}_score'
        is_home = 1 if team_type == 'home' else 0
        
        # Filter by home/away
        home_away_df = df[df.apply(lambda row: (row['home_team'] == row[team_col] and is_home == 1) or 
                                   (row['away_team'] == row[team_col] and is_home == 0), axis=1)]
        
        if len(home_away_df) > 0:
            feature_name = f'{team_type}_goals_avg_{"home" if is_home else "away"}'
            values = df.groupby(team_col)[goals_col].transform(
                lambda x: x.rolling(10, min_periods=1).mean().shift(1)
            )
            df.loc[:, feature_name] = values
    
    # Head-to-head history
    h2h_values = df.apply(
        lambda row: calculate_h2h_total_goals_avg(df, row['home_team'], row['away_team'], row['date']), 
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
    if 'odds_over_2_5' in df.columns:
        # Replace 0 with NaN to avoid division by zero
        odds_over = df['odds_over_2_5'].replace(0, np.nan).fillna(2.0)
        odds_under = df['odds_under_2_5'].replace(0, np.nan).fillna(2.0)
        
        df.loc[:, 'implied_prob_over'] = 1.0 / odds_over
        df.loc[:, 'implied_prob_under'] = 1.0 / odds_under
    
    # Fill NaN values with defaults and replace infinity
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    df.loc[:, numeric_cols] = df[numeric_cols].fillna(0)
    df.loc[:, numeric_cols] = df[numeric_cols].replace([np.inf, -np.inf], 0)
    
    return df

def engineer_btts_features(match_df: pd.DataFrame) -> pd.DataFrame:
    """Engineer features specifically for Both Teams To Score (BTTS) prediction."""
    logger.info("Engineering BTTS features")
    
    # Validate and prepare
    df = validate_and_prepare_dataframe(match_df, ['home_team', 'away_team'])
    if df.empty:
        return df
    
    # Create target variables if not already present
    if 'btts' not in df.columns:
        if 'home_score' in df.columns and 'away_score' in df.columns:
            if 'total_goals' not in df.columns:
                df.loc[:, 'total_goals'] = df['home_score'] + df['away_score']
            df.loc[:, 'btts'] = ((df['home_score'] > 0) & (df['away_score'] > 0)).astype(int)
            if 'over_2_5' not in df.columns:
                df.loc[:, 'over_2_5'] = (df['total_goals'] > 2.5).astype(int)
        else:
            logger.warning("home_score/away_score columns not found, cannot create btts target")
            df.loc[:, 'btts'] = np.nan
    
    # Team scoring consistency features
    for team_type in ['home', 'away']:
        team_col = f'{team_type}_team'
        goals_col = f'{team_type}_score'  # home_score or away_score
        opponent_goals_col = f'{"away" if team_type == "home" else "home"}_score'  # Opponent goals
        
        # Scoring rate
        df = add_binary_rate_features(df, team_col, goals_col, f'{team_type}_scoring', lambda x: x > 0)
        
        # Average goals scored
        df = add_rolling_averages(df, team_col, goals_col, f'{team_type}_goals', [5])
        df = add_expanding_average(df, team_col, goals_col, f'{team_type}_goals')
        
        # Scoreless frequency
        scoreless_values = df.groupby(team_col)[goals_col].transform(
            lambda x: (x == 0).expanding().mean().shift(1)
        )
        df.loc[:, f'{team_type}_scoreless_rate'] = scoreless_values
        
        # Conceding rate
        df = add_binary_rate_features(df, team_col, opponent_goals_col, f'{team_type}_conceding', lambda x: x > 0)
        
        # Clean sheet frequency
        clean_sheet_values = df.groupby(team_col)[opponent_goals_col].transform(
            lambda x: (x == 0).expanding().mean().shift(1)
        )
        df.loc[:, f'{team_type}_clean_sheet_rate'] = clean_sheet_values
    
    # Head-to-head BTTS history
    h2h_btts_values = df.apply(
        lambda row: calculate_h2h_btts_rate(df, row['home_team'], row['away_team'], row['date']),
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
    
    # Fill NaN values with defaults and replace infinity
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    df.loc[:, numeric_cols] = df[numeric_cols].fillna(0)
    df.loc[:, numeric_cols] = df[numeric_cols].replace([np.inf, -np.inf], 0)
    
    return df

def prepare_match_features_for_prediction(match_obj, historical_df: Optional[pd.DataFrame] = None):
    """
    Prepare features for a single match prediction.
    Wrapper to convert single match object to DataFrame and run pipelines.
    """
    # Convert match object to DataFrame row
    match_data = {
        'date': match_obj.start_time,
        'home_team': match_obj.home_team,
        'away_team': match_obj.away_team,
        'odds_over_2_5': match_obj.odds_over_2_5,
        'odds_under_2_5': match_obj.odds_under_2_5,
        'odds_btts_yes': match_obj.odds_btts_yes,
        'odds_btts_no': match_obj.odds_btts_no,
        # Add other necessary columns with None/NaN if missing
        'home_score': np.nan,
        'away_score': np.nan
    }
    
    current_match_df = pd.DataFrame([match_data])
    
    if historical_df is not None and not historical_df.empty:
        # Append current match to historical data to calculate rolling stats
        # Ensure columns match
        common_cols = list(set(historical_df.columns) & set(current_match_df.columns))
        
        # We need to append current match to the end
        combined_df = pd.concat([historical_df, current_match_df], ignore_index=True)
        combined_df = combined_df.sort_values('date')
        
        # Run pipelines
        features_over_under = engineer_over_under_2_5_features(combined_df)
        features_btts = engineer_btts_features(combined_df)
        
        # Run pipelines
        features_over_under = engineer_over_under_2_5_features(combined_df)
        features_btts = engineer_btts_features(combined_df)
        
        # Extract the specific row for our current match
        # We match on date, home_team, and away_team to be sure
        mask = (
            (features_over_under['date'] == match_obj.start_time) & 
            (features_over_under['home_team'] == match_obj.home_team) & 
            (features_over_under['away_team'] == match_obj.away_team)
        )
        
        current_features_ou = features_over_under[mask]
        current_features_btts = features_btts[mask]
        
        if current_features_ou.empty:
            logger.warning(f"Could not find current match in engineered features: {match_obj.home_team} vs {match_obj.away_team}")
            # Fallback to last row if not found (shouldn't happen)
            current_features_ou = features_over_under.iloc[[-1]]
            current_features_btts = features_btts.iloc[[-1]]
            
        return current_features_ou, current_features_btts
    else:
        # Fallback if no historical data (won't have rolling stats)
        return engineer_over_under_2_5_features(current_match_df), engineer_btts_features(current_match_df)
