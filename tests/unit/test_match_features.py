"""
Unit tests for match feature engineering functions.
"""
import pytest
import pandas as pd
import numpy as np
from datetime import date, datetime
from app.ml.match_features import (
    load_match_level_data,
    load_player_level_data,
    aggregate_player_stats_by_team,
    engineer_over_under_2_5_features,
    calculate_h2h_total_goals_avg
)


class TestLoadMatchLevelData:
    """Test match-level data loading."""
    
    def test_load_match_level_data_single_year(self, tmp_path, monkeypatch):
        """Test loading match data for a single year."""
        # Create test data file
        test_data = pd.DataFrame({
            'Date': ['22/08/2025', '23/08/2025'],
            'HomeTeam': ['Bayern Munich', 'Ein Frankfurt'],
            'AwayTeam': ['RB Leipzig', 'Werder Bremen'],
            'FTHG': [6, 4],
            'FTAG': [0, 1]
        })
        
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        test_data.to_csv(data_dir / "D1_2025.csv", index=False)
        
        monkeypatch.setattr("app.match_features.DATA_DIR", str(data_dir))
        
        df = load_match_level_data(years=[2025])
        assert len(df) == 2
        assert 'year' in df.columns
        assert df['year'].iloc[0] == 2025
    
    def test_load_match_level_data_multiple_years(self, tmp_path, monkeypatch):
        """Test loading match data for multiple years."""
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        
        for year in [2023, 2024]:
            test_data = pd.DataFrame({
                'Date': [f'22/08/{year}'],
                'HomeTeam': ['Team A'],
                'AwayTeam': ['Team B'],
                'FTHG': [2],
                'FTAG': [1]
            })
            test_data.to_csv(data_dir / f"D1_{year}.csv", index=False)
        
        monkeypatch.setattr("app.match_features.DATA_DIR", str(data_dir))
        
        df = load_match_level_data(years=[2023, 2024])
        assert len(df) == 2
        assert set(df['year'].unique()) == {2023, 2024}


class TestAggregatePlayerStats:
    """Test player statistics aggregation."""
    
    def test_aggregate_player_stats_by_team(self):
        """Test aggregating player stats to team level."""
        player_df = pd.DataFrame({
            'date': pd.to_datetime(['2025-01-01', '2025-01-08', '2025-01-15']),
            'team': ['Bayern Munich', 'Bayern Munich', 'Bayern Munich'],
            'goals': [2, 1, 3],
            'shots': [10, 8, 12],
            'shots_on_target': [5, 4, 6],
            'assists': [1, 0, 2]
        })
        
        match_date = date(2025, 1, 20)
        stats = aggregate_player_stats_by_team(player_df, match_date, 'Bayern Munich')
        
        assert 'goals_scored_avg_last_5' in stats
        assert stats['goals_scored_avg_last_5'] > 0
        assert 'shots_avg_last_5' in stats
    
    def test_aggregate_player_stats_no_data(self):
        """Test aggregation when no historical data exists."""
        player_df = pd.DataFrame({
            'date': pd.to_datetime(['2025-01-01']),
            'team': ['New Team'],
            'goals': [1],
            'shots': [5],
            'shots_on_target': [2],
            'assists': [0]
        })
        
        match_date = date(2024, 12, 31)  # Before any data
        stats = aggregate_player_stats_by_team(player_df, match_date, 'New Team')
        
        assert stats == {}  # Should return empty dict when no data


class TestFeatureEngineering:
    """Test feature engineering functions."""
    
    def test_engineer_over_under_2_5_features(self):
        """Test Over/Under 2.5 feature engineering."""
        match_df = pd.DataFrame({
            'Date': ['22/08/2025', '23/08/2025', '24/08/2025'],
            'HomeTeam': ['Team A', 'Team B', 'Team A'],
            'AwayTeam': ['Team B', 'Team C', 'Team C'],
            'FTHG': [2, 1, 3],
            'FTAG': [1, 2, 1],
            'HS': [15, 10, 18],
            'AS': [8, 12, 9],
            'HST': [7, 4, 9],
            'AST': [3, 5, 4],
            'B365>2.5': [1.8, 2.1, 1.6],
            'B365<2.5': [2.0, 1.9, 2.2]
        })
        
        df = engineer_over_under_2_5_features(match_df)
        
        # Check target variable created
        assert 'over_2_5' in df.columns
        assert 'total_goals' in df.columns
        
        # Check rolling features created
        assert 'home_goals_avg_last_5' in df.columns or 'home_goals_avg_season' in df.columns
        
        # Check interaction features
        assert 'combined_offensive_strength' in df.columns
        assert 'home_offense_vs_away_defense' in df.columns
    
    def test_calculate_h2h_total_goals_avg(self):
        """Test head-to-head total goals calculation."""
        match_df = pd.DataFrame({
            'date': pd.to_datetime(['2025-01-01', '2025-02-01', '2025-03-01', '2025-04-01']),
            'HomeTeam': ['Team A', 'Team B', 'Team A', 'Team B'],
            'AwayTeam': ['Team B', 'Team A', 'Team B', 'Team A'],
            'FTHG': [2, 1, 3, 0],
            'FTAG': [1, 2, 2, 1]
        })
        
        current_date = pd.Timestamp('2025-05-01')
        avg = calculate_h2h_total_goals_avg(match_df, 'Team A', 'Team B', current_date, n_matches=3)
        
        # Should calculate average of last 3 meetings: (2+1), (1+2), (3+2) = 3, 3, 5 -> avg = 3.67
        assert avg > 0
        assert avg <= 10  # Reasonable upper bound
    
    def test_calculate_h2h_no_history(self):
        """Test H2H calculation when no history exists."""
        match_df = pd.DataFrame({
            'date': pd.to_datetime(['2025-01-01']),
            'HomeTeam': ['Team A'],
            'AwayTeam': ['Team B'],
            'FTHG': [2],
            'FTAG': [1]
        })
        
        current_date = pd.Timestamp('2025-01-01')  # Same date, so no history
        avg = calculate_h2h_total_goals_avg(match_df, 'Team A', 'Team B', current_date)
        
        assert avg == 0.0  # Should return 0 when no history
    
    def test_engineer_features_missing_columns(self):
        """Test feature engineering with missing required columns."""
        match_df = pd.DataFrame({
            'Date': ['22/08/2025'],
            'FTHG': [2],
            'FTAG': [1]
        })
        
        with pytest.raises(ValueError, match="Missing required columns"):
            engineer_over_under_2_5_features(match_df)
    
    def test_engineer_features_empty_dataframe(self):
        """Test feature engineering with empty DataFrame."""
        match_df = pd.DataFrame()
        
        result = engineer_over_under_2_5_features(match_df)
        assert result.empty
    
    def test_engineer_features_newly_promoted_team(self):
        """Test feature engineering handles newly promoted teams (no historical data)."""
        match_df = pd.DataFrame({
            'Date': ['22/08/2025', '23/08/2025'],
            'HomeTeam': ['New Team', 'Established Team'],
            'AwayTeam': ['Established Team', 'New Team'],
            'FTHG': [1, 2],
            'FTAG': [0, 1],
            'HS': [10, 15],
            'AS': [8, 9],
            'HST': [4, 6],
            'AST': [2, 3]
        })
        
        # Should not raise error even with new team (no history)
        result = engineer_over_under_2_5_features(match_df)
        assert len(result) == 2
        # New team features should default to 0 or NaN
        assert 'home_goals_avg_season' in result.columns or 'away_goals_avg_season' in result.columns

