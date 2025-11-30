import asyncio
import sys
import os
from sqlalchemy import select, func

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.infrastructure.db.session import SessionLocal
from app.domain.models import Team, Match

async def investigate_duplicates():
    async with SessionLocal() as session:
        # Find teams with duplicate names but different league values
        stmt = select(Team).order_by(Team.name, Team.league)
        result = await session.execute(stmt)
        teams = result.scalars().all()
        
        print("=== Teams grouped by name ===")
        current_name = None
        for team in teams:
            if team.name != current_name:
                if current_name is not None:
                    print()
                current_name = team.name
                print(f"\n{team.name}:")
            print(f"  ID: {team.id}, League: {team.league}")
        
        # Check match statuses
        print("\n\n=== Match Status Distribution ===")
        stmt = select(Match.status, func.count(Match.id)).group_by(Match.status)
        result = await session.execute(stmt)
        for status, count in result.all():
            print(f"{status}: {count} matches")
        
        # Check matches with fixture_id but no team_id
        print("\n\n=== Matches with fixture_id but missing team_id ===")
        stmt = select(func.count(Match.id)).where(
            Match.fixture_id.isnot(None),
            (Match.home_team_id.is_(None) | Match.away_team_id.is_(None))
        )
        result = await session.execute(stmt)
        count = result.scalar()
        print(f"Found {count} matches with fixture_id but missing team_id")

if __name__ == "__main__":
    asyncio.run(investigate_duplicates())
