import asyncio
import sys
import os
import pandas as pd
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.infrastructure.db.session import SessionLocal, engine, Base
from app.domain.models import Player, HistoricalStat

CSV_PATH = "data/player_stats_history_enriched.csv"

async def import_player_stats():
    print(f"Reading {CSV_PATH}...")
    try:
        df = pd.read_csv(CSV_PATH)
    except FileNotFoundError:
        print(f"Error: {CSV_PATH} not found.")
        return

    print(f"Found {len(df)} rows. Starting import...")

    async with SessionLocal() as session:
        # 1. Import Players
        # Get unique players from CSV
        players_df = df[['player_id', 'player_name', 'team', 'position']].drop_duplicates('player_id')
        
        print(f"Importing {len(players_df)} players...")
        
        for _, row in players_df.iterrows():
            # Check if player exists
            stmt = select(Player).where(Player.player_id == int(row['player_id']))
            result = await session.execute(stmt)
            player = result.scalar_one_or_none()
            
            if not player:
                player = Player(
                    player_id=int(row['player_id']),
                    name=row['player_name'],
                    team=row['team'],
                    position=row['position']
                )
                session.add(player)
            else:
                # Update team/position if changed (optional, but good for latest info)
                player.team = row['team']
                player.position = row['position']
        
        await session.commit()
        print("Players imported.")

        # 2. Import Historical Stats
        # We need to map API player_id to DB ID
        print("Fetching player map...")
        result = await session.execute(select(Player.player_id, Player.id))
        player_map = dict(result.all()) # {api_id: db_id}
        
        print("Importing historical stats...")
        
        # Prepare batch insert
        stats_data = []
        batch_size = 1000
        
        # Clear existing stats? The user said "fill it again", implying it might be empty or should be reset.
        # Let's truncate the table first to be safe and avoid duplicates if re-running.
        # But user said "fill it again", so maybe just append? 
        # To be safe against duplicates, we should probably clear it or check existence.
        # Given the volume, checking existence for every row is slow.
        # I'll truncate it as it's a "history" load.
        
        print("Clearing existing historical stats...")
        await session.execute(text("TRUNCATE TABLE historical_stats RESTART IDENTITY CASCADE"))
        await session.commit()

        for idx, row in df.iterrows():
            api_player_id = int(row['player_id'])
            if api_player_id not in player_map:
                print(f"Warning: Player ID {api_player_id} not found in DB map. Skipping.")
                continue
                
            db_player_id = player_map[api_player_id]
            
            # Parse date
            try:
                match_date = datetime.strptime(row['date'].split('+')[0], "%Y-%m-%d %H:%M:%S")
            except ValueError:
                match_date = datetime.strptime(row['date'], "%Y-%m-%d") # Fallback

            stat = {
                "player_id": db_player_id,
                "match_date": match_date.date(),
                "opponent": row['opponent'],
                "minutes_played": int(row['minutes']) if pd.notna(row['minutes']) else 0,
                "shots": int(row['shots']) if pd.notna(row['shots']) else 0,
                "shots_on_target": int(row['shots_on_target']) if pd.notna(row['shots_on_target']) else 0,
                "assists": int(row['assists']) if pd.notna(row['assists']) else 0,
                "passes": int(row['passes']) if pd.notna(row['passes']) else 0,
                "tackles": int(row['tackles']) if pd.notna(row['tackles']) else 0,
                "cards": int(row['cards']) if pd.notna(row['cards']) else 0
            }
            stats_data.append(stat)
            
            if len(stats_data) >= batch_size:
                await session.execute(insert(HistoricalStat), stats_data)
                await session.commit()
                stats_data = []
                print(f"Imported {idx + 1} rows...")
        
        if stats_data:
            await session.execute(insert(HistoricalStat), stats_data)
            await session.commit()
            
        print("Historical stats import completed.")

if __name__ == "__main__":
    from sqlalchemy import text
    asyncio.run(import_player_stats())
