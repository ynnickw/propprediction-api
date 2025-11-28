from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean, Date
from sqlalchemy.orm import relationship
from app.infrastructure.db.session import Base
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
    
    # Match Scores
    home_score = Column(Integer, nullable=True)
    away_score = Column(Integer, nullable=True)
    home_half_time_goals = Column(Integer, nullable=True)
    away_half_time_goals = Column(Integer, nullable=True)
    
    # Match Statistics
    home_shots = Column(Integer, nullable=True)
    away_shots = Column(Integer, nullable=True)
    home_shots_on_target = Column(Integer, nullable=True)
    away_shots_on_target = Column(Integer, nullable=True)
    home_corners = Column(Integer, nullable=True)
    away_corners = Column(Integer, nullable=True)
    home_fouls = Column(Integer, nullable=True)
    away_fouls = Column(Integer, nullable=True)
    home_yellow_cards = Column(Integer, nullable=True)
    away_yellow_cards = Column(Integer, nullable=True)
    home_red_cards = Column(Integer, nullable=True)
    away_red_cards = Column(Integer, nullable=True)
    
    # Match Odds (1x2)
    odds_home = Column(Float, nullable=True)
    odds_draw = Column(Float, nullable=True)
    odds_away = Column(Float, nullable=True)
    
    # Match Prediction Odds
    odds_over_2_5 = Column(Float, nullable=True)
    odds_under_2_5 = Column(Float, nullable=True)
    odds_btts_yes = Column(Float, nullable=True)
    odds_btts_no = Column(Float, nullable=True)

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
    player_id = Column(Integer, ForeignKey("players.id"), nullable=True)  # Nullable for match-level picks
    match_id = Column(Integer, ForeignKey("matches.id"))
    
    player = relationship("Player")
    match = relationship("Match")
    prediction_type = Column(String, default='player_prop')  # 'player_prop', 'over_under_2.5', 'btts'
    prop_type = Column(String)
    line = Column(Float)
    recommendation = Column(String) # Over/Under/Yes/No
    model_expected = Column(Float)
    bookmaker_prob = Column(Float)
    model_prob = Column(Float)
    edge_percent = Column(Float)
    confidence = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    @property
    def player_name(self):
        return self.player.name if self.player else None

    @property
    def match_info(self):
        return f"{self.match.home_team} vs {self.match.away_team}" if self.match else None

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    api_key = Column(String, unique=True, index=True)
    is_active = Column(Boolean, default=True)
