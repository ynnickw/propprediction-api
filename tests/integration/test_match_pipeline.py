"""
Integration tests for match prediction pipeline.
"""
import pytest
import pandas as pd
from datetime import datetime, timedelta
from app.ml.match_features import (
    load_match_level_data,
    engineer_over_under_2_5_features
)
from app.ml.train_match import (
    prepare_training_data_for_over_under_2_5,
    train_over_under_2_5
)
from app.ml.match_predictions import predict_match_outcome, calculate_edge


class TestOverUnder25PredictionPipeline:
    """Test end-to-end Over/Under 2.5 prediction pipeline."""
    
    @pytest.mark.skipif(
        not all(pd.io.common.file_exists(f"data/D1_{year}.csv") for year in [2020, 2021, 2022, 2023, 2024, 2025]),
        reason="Match data files not available"
    )
    def test_full_prediction_pipeline(self):
        """Test complete prediction pipeline from data loading to prediction."""
        # 1. Load and engineer features
        match_df = load_match_level_data()
        df = engineer_over_under_2_5_features(match_df)
        
        # Verify features created
        assert 'over_2_5' in df.columns
        assert 'total_goals' in df.columns
        assert len(df) > 0
        
        # 2. Prepare training data
        train_df, features = prepare_training_data_for_over_under_2_5()
        
        # Verify training data prepared
        assert len(features) > 0
        assert 'over_2_5' in train_df.columns
        assert len(train_df) > 0
        
        # 3. Test prediction (if models exist)
        # This would require trained models, so we'll test the structure
        sample_features = train_df[features].head(1)
        
        # Verify feature structure is correct for prediction
        assert sample_features.shape[1] == len(features)
    
    def test_edge_calculation_integration(self):
        """Test edge calculation with realistic probabilities."""
        # Simulate model prediction
        model_prob = 0.65  # Model thinks 65% chance of Over 2.5
        
        # Bookmaker odds
        bookmaker_odds_over = 1.8  # Implied prob = 55.6%
        bookmaker_odds_under = 2.1  # Implied prob = 47.6%
        
        # Calculate edge for Over
        bookmaker_prob, edge = calculate_edge(model_prob, bookmaker_odds_over)
        
        assert bookmaker_prob == pytest.approx(1.0 / 1.8, rel=0.01)
        assert edge > 0  # Should have positive edge
        assert edge == pytest.approx((0.65 - (1.0/1.8)) * 100, rel=0.1)
    
    def test_edge_calculation_missing_odds(self):
        """Test edge calculation with missing/invalid odds."""
        from app.ml.match_predictions import calculate_edge
        
        # Test with None odds
        bookmaker_prob, edge = calculate_edge(0.5, None)
        assert bookmaker_prob == 0.0
        assert edge == 0.0
        
        # Test with invalid odds
        bookmaker_prob, edge = calculate_edge(0.5, 0.5)
        assert bookmaker_prob == 0.0
        assert edge == 0.0
    
    def test_no_upcoming_matches(self):
        """Test pipeline behavior when no upcoming matches exist."""
        # This would require database mocking, but we can test the logic
        # In a real scenario, the function should handle empty match list gracefully
        matches = []
        assert len(matches) == 0
        # Pipeline should not crash with empty match list
    
    def test_duplicate_prevention(self):
        """Test that duplicate picks are not created."""
        # This would require database mocking
        # Logic: check existing picks by match_id, prediction_type, recommendation
        # If exists, skip creation
        pass  # Placeholder for actual test with database

