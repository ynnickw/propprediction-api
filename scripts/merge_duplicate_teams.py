import asyncio
import sys
import os
from sqlalchemy import select, update, delete

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.infrastructure.db.session import SessionLocal
from app.domain.models import Team, Match
from app.config.constants import API_FOOTBALL_TO_DB_MAPPING

async def merge_duplicate_teams():
    """Merge duplicate teams created by API-Football into canonical teams."""
    async with SessionLocal() as session:
        # Build reverse mapping: API-Football name -> DB name
        duplicates_to_merge = {}
        for api_name, db_name in API_FOOTBALL_TO_DB_MAPPING.items():
            if api_name != db_name:
                duplicates_to_merge[api_name] = db_name
        
        print(f"Found {len(duplicates_to_merge)} potential duplicate mappings")
        
        for api_name, canonical_name in duplicates_to_merge.items():
            # Find the duplicate team (API-Football name)
            stmt = select(Team).where(Team.name == api_name)
            result = await session.execute(stmt)
            duplicate_team = result.scalar_one_or_none()
            
            if not duplicate_team:
                continue
            
            # Find the canonical team (historical data name)
            stmt = select(Team).where(Team.name == canonical_name)
            result = await session.execute(stmt)
            canonical_team = result.scalar_one_or_none()
            
            if not canonical_team:
                print(f"Warning: Canonical team '{canonical_name}' not found for '{api_name}'")
                continue
            
            print(f"Merging '{api_name}' (ID: {duplicate_team.id}) -> '{canonical_name}' (ID: {canonical_team.id})")
            
            # Update all matches using the duplicate team
            # Update home_team_id
            stmt = (
                update(Match)
                .where(Match.home_team_id == duplicate_team.id)
                .values(home_team_id=canonical_team.id)
            )
            result = await session.execute(stmt)
            print(f"  Updated {result.rowcount} matches (home_team_id)")
            
            # Update away_team_id
            stmt = (
                update(Match)
                .where(Match.away_team_id == duplicate_team.id)
                .values(away_team_id=canonical_team.id)
            )
            result = await session.execute(stmt)
            print(f"  Updated {result.rowcount} matches (away_team_id)")
            
            # Delete the duplicate team
            stmt = delete(Team).where(Team.id == duplicate_team.id)
            await session.execute(stmt)
            print(f"  Deleted duplicate team '{api_name}'")
        
        await session.commit()
        print("Done merging duplicate teams!")

if __name__ == "__main__":
    asyncio.run(merge_duplicate_teams())
