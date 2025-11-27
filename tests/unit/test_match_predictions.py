"""
Unit tests for match prediction functions.
"""
import pytest
import pandas as pd
import numpy as np
from app.ml.match_predictions import (
    calculate_edge,
    filter_picks_by_edge
)


class TestEdgeCalculation:
    """Test edge calculation functions."""
    
    def test_calculate_edge_positive(self):
        """Test edge calculation with positive edge."""
        model_prob = 0.6  # 60% model probability
        bookmaker_odds = 2.0  # Implied probability = 50%
        
        bookmaker_prob, edge = calculate_edge(model_prob, bookmaker_odds)
        
        assert bookmaker_prob == 0.5
        assert edge == 10.0  # 10% edge
    
    def test_calculate_edge_negative(self):
        """Test edge calculation with negative edge."""
        model_prob = 0.4  # 40% model probability
        bookmaker_odds = 2.0  # Implied probability = 50%
        
        bookmaker_prob, edge = calculate_edge(model_prob, bookmaker_odds)
        
        assert bookmaker_prob == 0.5
        assert edge == -10.0  # -10% edge (no value)
    
    def test_calculate_edge_invalid_odds(self):
        """Test edge calculation with invalid odds."""
        model_prob = 0.5
        bookmaker_odds = 0.5  # Invalid (<= 1.0)
        
        bookmaker_prob, edge = calculate_edge(model_prob, bookmaker_odds)
        
        assert bookmaker_prob == 0.0
        assert edge == 0.0


class TestFilterPicks:
    """Test pick filtering functions."""
    
    def test_filter_picks_by_edge(self):
        """Test filtering picks by minimum edge threshold."""
        predictions = [
            {'edge_percent': 12.0, 'match_id': 1},
            {'edge_percent': 5.0, 'match_id': 2},
            {'edge_percent': 15.0, 'match_id': 3},
            {'edge_percent': 8.0, 'match_id': 4},
            {'edge_percent': 3.0, 'match_id': 5}
        ]
        
        filtered = filter_picks_by_edge(predictions, min_edge=8.0)
        
        assert len(filtered) == 3
        assert all(p['edge_percent'] >= 8.0 for p in filtered)
        assert filtered[0]['match_id'] == 1
        assert filtered[1]['match_id'] == 3
        assert filtered[2]['match_id'] == 4
    
    def test_filter_picks_all_below_threshold(self):
        """Test filtering when all picks are below threshold."""
        predictions = [
            {'edge_percent': 5.0, 'match_id': 1},
            {'edge_percent': 3.0, 'match_id': 2}
        ]
        
        filtered = filter_picks_by_edge(predictions, min_edge=8.0)
        
        assert len(filtered) == 0
    
    def test_filter_picks_empty_list(self):
        """Test filtering empty prediction list."""
        predictions = []
        
        filtered = filter_picks_by_edge(predictions, min_edge=8.0)
        
        assert len(filtered) == 0

