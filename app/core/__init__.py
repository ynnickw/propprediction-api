"""
Core infrastructure for FootProp AI Backend.

Contains database, models, schemas, and utilities.
"""

from .database import get_db, engine, Base, SessionLocal
from .models import Match, Player, PropLine, HistoricalStat, DailyPick, User
from .schemas import PickResponse, LeagueResponse, HealthResponse

__all__ = [
    "get_db",
    "engine",
    "Base",
    "SessionLocal",
    "Match",
    "Player",
    "PropLine",
    "HistoricalStat",
    "DailyPick",
    "User",
    "PickResponse",
    "LeagueResponse",
    "HealthResponse",
]

