import asyncio
import os
import sys
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Add project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import DATABASE_URL
from app.core.models import Match

async def inspect_odds():
    engine = create_async_engine(DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Check for specific matches mentioned in logs
        matches_to_check = [
            ("FSV Mainz 05", "Borussia Mönchengladbach"),
            ("1.FC Köln", "FC St. Pauli"),
            ("VfL Wolfsburg", "Union Berlin")
        ]

        for home, away in matches_to_check:
            stmt = select(Match).where(Match.home_team == home, Match.away_team == away)
            result = await session.execute(stmt)
            match = result.scalars().first()

            if match:
                print(f"\nMatch: {match.home_team} vs {match.away_team}")
                print(f"  Status: {match.status}")
                print(f"  Start Time: {match.start_time}")
                print(f"  Odds Over 2.5: {match.odds_over_2_5}")
                print(f"  Odds Under 2.5: {match.odds_under_2_5}")
                print(f"  Odds BTTS Yes: {match.odds_btts_yes}")
                print(f"  Odds BTTS No: {match.odds_btts_no}")
                print(f"  Odds Home: {match.odds_home}")
                print(f"  Odds Draw: {match.odds_draw}")
                print(f"  Odds Away: {match.odds_away}")
            else:
                print(f"\nMatch not found: {home} vs {away}")

if __name__ == "__main__":
    asyncio.run(inspect_odds())
