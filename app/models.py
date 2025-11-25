from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean, Date
from sqlalchemy.orm import relationship
from .database import Base
from datetime import datetime

class Match(Base):
    __tablename__ = "matches"

    id = Column(Integer, primary_key=True, index=True)
    fixture_id = Column(Integer, unique=True, index=True)
    league_id = Column(Integer)
    home_team = Column(String)
    away_team = Column(String)
    start_time = Column(DateTime)
    status = Column(String)
    
    # Match Odds (1x2)
    odds_home = Column(Float, nullable=True)
    odds_draw = Column(Float, nullable=True)
    odds_away = Column(Float, nullable=True)

    prop_lines = relationship("PropLine", back_populates="match")

class Player(Base):
    __tablename__ = "players"

    id = Column(Integer, primary_key=True, index=True)
    player_id = Column(Integer, unique=True, index=True) # API Football ID
    name = Column(String)
    team = Column(String)
    position = Column(String)

    prop_lines = relationship("PropLine", back_populates="player")
    historical_stats = relationship("HistoricalStat", back_populates="player")

class PropLine(Base):
    __tablename__ = "prop_lines"

    id = Column(Integer, primary_key=True, index=True)
    match_id = Column(Integer, ForeignKey("matches.id"))
    player_id = Column(Integer, ForeignKey("players.id"))
    prop_type = Column(String) # shots, shots_on_target, etc.
    line = Column(Float)
    odds_over = Column(Float)
    odds_under = Column(Float)
    bookmaker = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)

    match = relationship("Match", back_populates="prop_lines")
    player = relationship("Player", back_populates="prop_lines")

class HistoricalStat(Base):
    __tablename__ = "historical_stats"

    id = Column(Integer, primary_key=True, index=True)
    player_id = Column(Integer, ForeignKey("players.id"))
    match_date = Column(Date)
    opponent = Column(String)
    minutes_played = Column(Integer)
    shots = Column(Integer)
    shots_on_target = Column(Integer)
    assists = Column(Integer)
    passes = Column(Integer)
    tackles = Column(Integer)
    cards = Column(Integer) # Yellow + Red

    player = relationship("Player", back_populates="historical_stats")

class DailyPick(Base):
    __tablename__ = "daily_picks"

    id = Column(Integer, primary_key=True, index=True)
    player_name = Column(String)
    match_info = Column(String)
    prop_type = Column(String)
    line = Column(Float)
    recommendation = Column(String) # Over/Under
    model_expected = Column(Float)
    bookmaker_prob = Column(Float)
    model_prob = Column(Float)
    edge_percent = Column(Float)
    confidence = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    api_key = Column(String, unique=True, index=True)
    is_active = Column(Boolean, default=True)
