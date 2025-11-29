import pandas as pd
from typing import List
from sqlalchemy import create_engine
from app.config import settings
import structlog

logger = structlog.get_logger()

def load_match_level_data(years: List[int] = None) -> pd.DataFrame:
    """Load match-level datasets from the database."""
    database_url = settings.DATABASE_URL
    if not database_url:
        raise ValueError("DATABASE_URL not set")
        
    # Handle async driver for sync pandas connection
    if database_url.startswith("postgresql+asyncpg"):
        database_url = database_url.replace("postgresql+asyncpg", "postgresql")
        
    # Handle docker host for local execution
    if "host.docker.internal" in database_url:
        database_url = database_url.replace("host.docker.internal", "localhost")
        
    engine = create_engine(database_url)
    
    query = """
    SELECT 
        m.start_time as "date",
        ht.name as home_team,
        at.name as away_team,
        m.home_score,
        m.away_score,
        m.home_half_time_goals,
        m.away_half_time_goals,
        m.home_shots,
        m.away_shots,
        m.home_shots_on_target,
        m.away_shots_on_target,
        m.home_corners,
        m.away_corners,
        m.home_fouls,
        m.away_fouls,
        m.home_yellow_cards,
        m.away_yellow_cards,
        m.home_red_cards,
        m.away_red_cards,
        m.odds_home,
        m.odds_draw,
        m.odds_away,
        m.odds_over_2_5,
        m.odds_under_2_5,
        m.odds_btts_yes,
        m.odds_btts_no
    FROM matches m
    JOIN teams ht ON m.home_team_id = ht.id
    JOIN teams at ON m.away_team_id = at.id
    """
    
    logger.info("Loading match data from database")
    try:
        df = pd.read_sql(query, engine)
        
        # Ensure date is datetime
        df.loc[:, 'date'] = pd.to_datetime(df['date'])
        
        # Ensure numeric columns are float (handle None/NULL from DB)
        numeric_cols = [
            'home_score', 'away_score', 'home_half_time_goals', 'away_half_time_goals',
            'home_shots', 'away_shots', 'home_shots_on_target', 'away_shots_on_target',
            'home_corners', 'away_corners', 'home_fouls', 'away_fouls',
            'home_yellow_cards', 'away_yellow_cards', 'home_red_cards', 'away_red_cards',
            'odds_home', 'odds_draw', 'odds_away', 'odds_over_2_5', 'odds_under_2_5',
            'odds_btts_yes', 'odds_btts_no'
        ]
        
        for col in numeric_cols:
            if col in df.columns:
                df.loc[:, col] = pd.to_numeric(df[col], errors='coerce')
        
        # Add year column for compatibility
        df.loc[:, 'year'] = df['date'].dt.year
        
        logger.info(f"Loaded {len(df)} match records from database")
        return df
        
    except Exception as e:
        logger.error(f"Failed to load data from database: {e}")
        raise
