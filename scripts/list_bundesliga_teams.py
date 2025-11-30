import asyncio
import sys
import os
from sqlalchemy import select

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.infrastructure.db.session import SessionLocal
from app.domain.models import Team

async def list_bundesliga_teams():
    async with SessionLocal() as session:
        # Find all Bundesliga teams
        stmt = select(Team).where(Team.league == "Bundesliga").order_by(Team.name)
        result = await session.execute(stmt)
        teams = result.scalars().all()
        
        print(f"=== Bundesliga Teams ({len(teams)} total) ===\n")
        
        # Group by name to find duplicates
        teams_by_name = {}
        for team in teams:
            if team.name not in teams_by_name:
                teams_by_name[team.name] = []
            teams_by_name[team.name].append(team)
        
        # Print all teams
        for name, team_list in sorted(teams_by_name.items()):
            if len(team_list) > 1:
                print(f"⚠️  {name} (DUPLICATE - {len(team_list)} entries):")
                for team in team_list:
                    print(f"    ID: {team.id}, League: {team.league}")
            else:
                print(f"✓  {name} (ID: {team_list[0].id})")
        
        print(f"\n\nTotal unique team names: {len(teams_by_name)}")
        print(f"Total team entries: {len(teams)}")
        print(f"Duplicates: {len(teams) - len(teams_by_name)}")

if __name__ == "__main__":
    asyncio.run(list_bundesliga_teams())
