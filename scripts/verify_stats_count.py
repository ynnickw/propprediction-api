import asyncio
import sys
import os
from sqlalchemy import select, func

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.infrastructure.db.session import SessionLocal
from app.domain.models import Match

async def check_odds():
    async with SessionLocal() as session:
        # Count total matches
        total = await session.scalar(select(func.count(Match.id)))
        
        # Count matches with BTTS odds
        btts_yes = await session.scalar(select(func.count(Match.id)).where(Match.odds_btts_yes.is_not(None)))
        
        # Count matches with Over/Under odds
        over_2_5 = await session.scalar(select(func.count(Match.id)).where(Match.odds_over_2_5.is_not(None)))
        
        print(f"Total Matches: {total}")
        print(f"Matches with BTTS Odds: {btts_yes} ({btts_yes/total*100:.1f}%)")
        print(f"Matches with O/U Odds: {over_2_5} ({over_2_5/total*100:.1f}%)")

if __name__ == "__main__":
    asyncio.run(check_odds())
