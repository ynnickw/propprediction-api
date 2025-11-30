import asyncio
import sys
import os
from sqlalchemy import select, func

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.infrastructure.db.session import SessionLocal
from app.domain.models import Match

async def count_matches():
    async with SessionLocal() as session:
        # Count total matches
        total = await session.scalar(select(func.count(Match.id)))
        
        # Count finished matches (status 'FT')
        finished = await session.scalar(select(func.count(Match.id)).where(Match.status == "FT"))
        
        # Count matches with scores
        with_scores = await session.scalar(select(func.count(Match.id)).where(Match.home_score.isnot(None)))
        
        print(f"Total Matches: {total}")
        print(f"Finished Matches (FT): {finished}")
        print(f"Matches with Scores: {with_scores}")

if __name__ == "__main__":
    asyncio.run(count_matches())
