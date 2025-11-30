import asyncio
import sys
import os
from sqlalchemy import select, update, delete

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.infrastructure.db.session import SessionLocal
from app.domain.models import Team, Match

async def merge_league_78_teams():
    """Merge teams with league='78' into their Bundesliga counterparts."""
    async with SessionLocal() as session:
        # Find all teams with league='78'
        stmt = select(Team).where(Team.league == "78")
        result = await session.execute(stmt)
        league_78_teams = result.scalars().all()
        
        print(f"Found {len(league_78_teams)} teams with league='78'")
        
        for team_78 in league_78_teams:
            # Find the Bundesliga counterpart
            stmt = select(Team).where(
                Team.name == team_78.name,
                Team.league == "Bundesliga"
            )
            result = await session.execute(stmt)
            bundesliga_team = result.scalar_one_or_none()
            
            if bundesliga_team:
                print(f"\nMerging '{team_78.name}' (ID: {team_78.id}, League: 78) -> (ID: {bundesliga_team.id}, League: Bundesliga)")
                
                # Update all matches using the league=78 team
                # Update home_team_id
                stmt = (
                    update(Match)
                    .where(Match.home_team_id == team_78.id)
                    .values(home_team_id=bundesliga_team.id)
                )
                result = await session.execute(stmt)
                print(f"  Updated {result.rowcount} matches (home_team_id)")
                
                # Update away_team_id
                stmt = (
                    update(Match)
                    .where(Match.away_team_id == team_78.id)
                    .values(away_team_id=bundesliga_team.id)
                )
                result = await session.execute(stmt)
                print(f"  Updated {result.rowcount} matches (away_team_id)")
                
                # Delete the league=78 team
                stmt = delete(Team).where(Team.id == team_78.id)
                await session.execute(stmt)
                print(f"  Deleted team with league='78'")
            else:
                # No Bundesliga counterpart found, just update the league value
                print(f"\nNo Bundesliga counterpart for '{team_78.name}', updating league value")
                stmt = (
                    update(Team)
                    .where(Team.id == team_78.id)
                    .values(league="Bundesliga")
                )
                await session.execute(stmt)
                print(f"  Updated league from '78' to 'Bundesliga'")
        
        await session.commit()
        print("\nDone merging teams with league='78'!")

if __name__ == "__main__":
    asyncio.run(merge_league_78_teams())
