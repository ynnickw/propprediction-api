import asyncio
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text, select, desc
from sqlalchemy.orm import joinedload
from app.infrastructure.db.session import SessionLocal
from app.domain.models import Match, DailyPick
import pandas as pd

async def show_probabilities():
    async with SessionLocal() as session:
        # Query picks for match-level predictions
        stmt = (
            select(DailyPick, Match)
            .join(Match, DailyPick.match_id == Match.id)
            .options(
                joinedload(Match.home_team_obj),
                joinedload(Match.away_team_obj)
            )
            .where(DailyPick.prediction_type.in_(['over_under_2.5', 'btts']))
            .order_by(desc(DailyPick.created_at))
            .limit(50)
        )
        
        result = await session.execute(stmt)
        rows = result.all()
        
        if not rows:
            print("No match-level picks found.")
            return

        print(f"{'Match':<40} | {'Type':<15} | {'Rec':<5} | {'Exp Val':<8} | {'Prob':<8} | {'Bookie %':<8} | {'Edge %':<8} | {'Created At':<20}")
        print("-" * 120)
        
        for pick, match in rows:
            match_str = f"{match.home_team} vs {match.away_team}"
            created_at = pick.created_at.strftime('%Y-%m-%d %H:%M:%S') if pick.created_at else "N/A"
            
            model_expected = f"{pick.model_expected:.2f}" if pick.model_expected is not None else "N/A"
            model_prob_str = f"{pick.model_prob*100:.1f}%" if pick.model_prob is not None else "N/A"
            bookie_prob = f"{pick.bookmaker_prob*100:.1f}%" if pick.bookmaker_prob else "N/A"
            edge = f"{pick.edge_percent:.1f}%" if pick.edge_percent else "N/A"
            
            print(f"{match_str:<40} | {pick.prediction_type:<15} | {pick.recommendation:<5} | {model_expected:<8} | {model_prob_str:<8} | {bookie_prob:<8} | {edge:<8} | {created_at:<20}")

if __name__ == "__main__":
    asyncio.run(show_probabilities())
