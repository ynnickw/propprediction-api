import asyncio
import sys
import os
from sqlalchemy import select, func

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal
from app.core.models import Match

async def check_duplicates():
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
        
        if duplicates:
            print(f"Found {len(duplicates)} duplicate match pairs:")
            for home, away, count in duplicates:
                print(f"  {home} vs {away}: {count} matches")
        else:
            print("No duplicate 'NS' matches found.")

if __name__ == "__main__":
    asyncio.run(check_duplicates())
