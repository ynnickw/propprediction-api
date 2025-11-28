import asyncio
import sys
import os
from sqlalchemy import select, func, delete

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal
from app.core.models import Match

async def cleanup_duplicates():
    async with SessionLocal() as session:
        # Find matches with same home, away, and status='NS'
        stmt = (
            select(Match.home_team, Match.away_team, func.count(Match.id))
            .where(Match.status == 'NS')
            .group_by(Match.home_team, Match.away_team)
            .having(func.count(Match.id) > 1)
        )
        
        result = await session.execute(stmt)
        duplicates = result.all()
        
        if not duplicates:
            print("No duplicates found.")
            return

        print(f"Found {len(duplicates)} duplicate pairs. Cleaning up...")
        
        for home, away, count in duplicates:
            print(f"Processing {home} vs {away}...")
            
            # Get all matches for this pair
            stmt_matches = (
                select(Match)
                .where(
                    Match.home_team == home,
                    Match.away_team == away,
                    Match.status == 'NS'
                )
                .order_by(Match.id)
            )
            result_matches = await session.execute(stmt_matches)
            matches = result_matches.scalars().all()
            
            # Keep the first one, delete the rest
            keep_match = matches[0]
            delete_matches = matches[1:]
            
            print(f"  Keeping match ID {keep_match.id}")
            for m in delete_matches:
                print(f"  Deleting match ID {m.id}")
                await session.delete(m)
                
        await session.commit()
        print("Cleanup complete.")

if __name__ == "__main__":
    asyncio.run(cleanup_duplicates())
