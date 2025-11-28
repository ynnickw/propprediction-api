"""
Data ingestion and collection module.

Handles fetching data from external APIs and preparing datasets.
"""

from .data_ingestion import (
    run_ingestion,
    fetch_upcoming_matches,
    fetch_prop_lines,
    fetch_match_odds,
    fetch_player_stats,
    LEAGUES,
    SPORT_KEYS
)

__all__ = [
    "run_ingestion",
    "fetch_upcoming_matches",
    "fetch_prop_lines",
    "fetch_match_odds",
    "fetch_player_stats",
    "LEAGUES",
    "SPORT_KEYS",
]

