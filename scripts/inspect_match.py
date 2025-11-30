import asyncio
import sys
import os
from sqlalchemy import select
from sqlalchemy.orm import aliased

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.infrastructure.db.session import SessionLocal
from app.domain.models import Match, Team

async def inspect_match():
    async with SessionLocal() as session:
        HomeTeam = aliased(Team)
        AwayTeam = aliased(Team)
        
        # Look for the match
        stmt = (
            select(Match, HomeTeam.name, AwayTeam.name)
            .join(HomeTeam, Match.home_team_id == HomeTeam.id)
            .join(AwayTeam, Match.away_team_id == AwayTeam.id)
            .where(
                HomeTeam.name == "Bayer Leverkusen",
                AwayTeam.name == "Borussia Dortmund"
            )
        )
        result = await session.execute(stmt)
        match_row = result.first()
        
        if match_row:
            match, home_name, away_name = match_row
            print(f"Match Found: {home_name} vs {away_name}")
            print(f"  ID: {match.id}")
            print(f"  Status: {match.status}")
            print(f"  Home Team ID: {match.home_team_id}")
            print(f"  Away Team ID: {match.away_team_id}")
            print(f"  Odds Over 2.5: {match.odds_over_2_5}")
        else:
            print("Match NOT found with exact names.")
            
            # List all matches involving Bayer Leverkusen
            print("\nMatches involving Bayer Leverkusen:")
            stmt = (
                select(Match, HomeTeam.name, AwayTeam.name)
                .join(HomeTeam, Match.home_team_id == HomeTeam.id)
                .join(AwayTeam, Match.away_team_id == AwayTeam.id)
                .where(HomeTeam.name == "Bayer Leverkusen")
            )
            result = await session.execute(stmt)
            for row in result.all():
                m, h, a = row
                print(f"  {h} vs {a} (Status: {m.status})")

if __name__ == "__main__":
    asyncio.run(inspect_match())
