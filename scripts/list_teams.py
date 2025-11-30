import asyncio
import sys
import os
from sqlalchemy import select

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.infrastructure.db.session import SessionLocal
from app.domain.models import Team

async def list_teams():
    async with SessionLocal() as session:
        stmt = select(Team.name).order_by(Team.name)
        result = await session.execute(stmt)
        teams = result.scalars().all()
        
        print(f"Found {len(teams)} teams:")
        for team in teams:
            print(team)

if __name__ == "__main__":
    asyncio.run(list_teams())
