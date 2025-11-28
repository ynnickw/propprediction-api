import asyncio
import sys
import os
from sqlalchemy import select, distinct

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal
from app.core.models import Match

async def check_team_names():
    async with SessionLocal() as session:
        # Check for Borussia
        stmt = select(distinct(Match.home_team)).where(Match.home_team.ilike('%Borussia%'))
        result = await session.execute(stmt)
        teams = result.scalars().all()
        print("Teams matching 'Borussia':")
        for team in teams:
            print(f"  '{team}'")
            
        # Check for Leipzig
        stmt = select(distinct(Match.home_team)).where(Match.home_team.ilike('%Leipzig%'))
        result = await session.execute(stmt)
        teams = result.scalars().all()
        print("\nTeams matching 'Leipzig':")
        for team in teams:
            print(f"  '{team}'")

if __name__ == "__main__":
    asyncio.run(check_team_names())
