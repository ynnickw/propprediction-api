import pytest
from app.features import calculate_rolling_averages
from app.models import HistoricalStat

def test_calculate_rolling_averages():
    stats = [
        HistoricalStat(shots=2, shots_on_target=1),
        HistoricalStat(shots=4, shots_on_target=2),
        HistoricalStat(shots=0, shots_on_target=0),
    ]
    
    avg = calculate_rolling_averages(stats, window=3)
    assert avg['shots'] == 2.0
    assert avg['shots_on_target'] == 1.0

def test_calculate_rolling_averages_empty():
    avg = calculate_rolling_averages([], window=5)
    assert avg == {}
