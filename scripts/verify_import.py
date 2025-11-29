import asyncio
import sys
import os
from sqlalchemy import select, func

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.infrastructure.db.session import SessionLocal
from app.domain.models import Match, Team

async def verify_import():
    async with SessionLocal() as session:
        # Check Teams
        stmt = select(func.count(Team.id))
        team_count = (await session.execute(stmt)).scalar()
        print(f"Total Teams: {team_count}")
        
        # Check Matches
        stmt = select(func.count(Match.id))
        match_count = (await session.execute(stmt)).scalar()
        print(f"Total Matches: {match_count}")
        
        # Check Relationships
        stmt = select(Match).limit(1)
        match = (await session.execute(stmt)).scalar_one_or_none()
        if match:
            # Eager load not strictly needed for scalar access if session open, 
            # but accessing properties that rely on relationships
            # We need to make sure we can access home_team property
            # Since we are in async, we might need to load them if not eager loaded by default query
            # But let's try accessing the property which uses the relationship
            try:
                # To access relationship in async, we usually need eager load or awaitable attribute
                # But here we are just checking if the ID is set
                print(f"Sample Match: {match.home_team_id} vs {match.away_team_id}")
                # Fetch teams manually to verify
                home_team = await session.get(Team, match.home_team_id)
                away_team = await session.get(Team, match.away_team_id)
                print(f"Sample Match Teams: {home_team.name} vs {away_team.name}")
            except Exception as e:
                print(f"Error accessing relationships: {e}")

        # Check for upcoming matches
        stmt = select(func.count(Match.id)).where(Match.status == 'NS')
        ns_count = (await session.execute(stmt)).scalar()
        print(f"Upcoming Matches (NS): {ns_count}")

if __name__ == "__main__":
    asyncio.run(verify_import())
