import asyncio
import sys
import os
from sqlalchemy import select, desc
from sqlalchemy.orm import joinedload

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.infrastructure.db.session import SessionLocal
from app.domain.models import Match, DailyPick

async def inspect_pick():
    async with SessionLocal() as session:
        # Get the latest pick
        stmt = (
            select(DailyPick)
            .options(
                joinedload(DailyPick.match).joinedload(Match.home_team_obj),
                joinedload(DailyPick.match).joinedload(Match.away_team_obj)
            )
            .order_by(desc(DailyPick.created_at))
            .limit(1)
        )
        
        result = await session.execute(stmt)
        pick = result.scalar_one_or_none()
        
        if not pick:
            print("No picks found.")
            return
            
        print(f"Pick ID: {pick.id}")
        print(f"Match: {pick.match.home_team} vs {pick.match.away_team}")
        print(f"Type: {pick.prediction_type}")
        print(f"Recommendation: {pick.recommendation}")
        print(f"Model Expected: {pick.model_expected}")
        print(f"Model Prob: {pick.model_prob}")
        print(f"Bookmaker Prob: {pick.bookmaker_prob}")
        print(f"Edge: {pick.edge_percent}")
        print(f"Odds: {pick.odds}")
        
        # Inspect Match Data
        match = pick.match
        print("\nMatch Data:")
        print(f"ID: {match.id}")
        print(f"Date: {match.date}")
        print(f"Status: {match.status}")
        print(f"Home Team ID: {match.home_team_id}")
        print(f"Away Team ID: {match.away_team_id}")
        print(f"Odds Over 2.5: {match.odds_over_2_5}")
        print(f"Odds Under 2.5: {match.odds_under_2_5}")
        print(f"Odds BTTS Yes: {match.odds_btts_yes}")
        print(f"Odds BTTS No: {match.odds_btts_no}")

if __name__ == "__main__":
    asyncio.run(inspect_pick())
