import asyncio
import pandas as pd
import os
from datetime import datetime
from sqlalchemy import select
from app.models import Match, Player, HistoricalStat
from app.database import SessionLocal
import structlog

logger = structlog.get_logger()

DATA_FILE = "data/player_stats_history_enriched.csv"

async def migrate_data():
    if not os.path.exists(DATA_FILE):
        logger.error(f"Data file not found: {DATA_FILE}")
        return

    logger.info(f"Loading data from {DATA_FILE}...")
    df = pd.read_csv(DATA_FILE)
    
    # Ensure date is datetime
    df['date'] = pd.to_datetime(df['date'])
    
    logger.info(f"Found {len(df)} records. Starting migration...")
    
    async with SessionLocal() as session:
        # Cache existing players and matches to minimize DB queries
        # In a massive migration, we might want to batch this, but for < 100k rows it's okay-ish
        # or just query as we go with a local dict cache
        
        existing_players = {} # player_id (api) -> db_id
        existing_matches = {} # fixture_id -> db_id
        
        # Pre-fetch players
        result = await session.execute(select(Player))
        for p in result.scalars().all():
            existing_players[p.player_id] = p.id
            
        # Pre-fetch matches
        result = await session.execute(select(Match))
        for m in result.scalars().all():
            if m.fixture_id:
                existing_matches[m.fixture_id] = m.id
                
        logger.info(f"Pre-loaded {len(existing_players)} players and {len(existing_matches)} matches.")
        
        stats_buffer = []
        
        for idx, row in df.iterrows():
            if idx % 1000 == 0:
                logger.info(f"Processing row {idx}/{len(df)}")
                
            # 1. Handle Player
            pid = row['player_id']
            if pid not in existing_players:
                new_player = Player(
                    player_id=pid,
                    name=row['player_name'],
                    team=row['team'],
                    position=row['position']
                )
                session.add(new_player)
                await session.flush() # Get ID
                existing_players[pid] = new_player.id
            
            player_db_id = existing_players[pid]
            
            # 2. Handle Match
            fid = row['fixture_id']
            if fid not in existing_matches:
                # Determine home/away
                if row['is_home'] == 1:
                    home = row['team']
                    away = row['opponent']
                else:
                    home = row['opponent']
                    away = row['team']
                    
                new_match = Match(
                    fixture_id=fid,
                    league_id=78, # Bundesliga
                    home_team=home,
                    away_team=away,
                    start_time=row['date'],
                    status='FT',
                    odds_home=row.get('B365H'),
                    odds_draw=row.get('B365D'),
                    odds_away=row.get('B365A')
                )
                session.add(new_match)
                await session.flush()
                existing_matches[fid] = new_match.id
                
            match_db_id = existing_matches[fid]
            
            # 3. Handle Historical Stat
            stat = HistoricalStat(
                player_id=player_db_id,
                match_date=row['date'].date(),
                opponent=row['opponent'],
                minutes_played=row['minutes'],
                shots=row['shots'],
                shots_on_target=row['shots_on_target'],
                assists=row['assists'],
                passes=row.get('passes', 0),
                tackles=row.get('tackles', 0),
                cards=row.get('cards', 0)
            )
            stats_buffer.append(stat)
            
            if len(stats_buffer) >= 1000:
                session.add_all(stats_buffer)
                await session.commit()
                stats_buffer = []
        
        # Commit remaining
        if stats_buffer:
            session.add_all(stats_buffer)
            await session.commit()
            
    logger.info("Migration complete!")

if __name__ == "__main__":
    asyncio.run(migrate_data())
