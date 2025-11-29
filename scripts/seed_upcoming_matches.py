import asyncio
import sys
import os
from datetime import datetime, timedelta
from sqlalchemy import select

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.infrastructure.db.session import SessionLocal
from app.domain.models import Match, Team

async def seed_upcoming_matches():
    async with SessionLocal() as session:
        # Get some teams
        stmt = select(Team).limit(4)
        teams = (await session.execute(stmt)).scalars().all()
        
        if len(teams) < 4:
            print("Not enough teams to seed matches")
            return
            
        t1, t2, t3, t4 = teams[:4]
        
        matches = [
            Match(
                league_id=1,
                home_team_id=t1.id,
                away_team_id=t2.id,
                start_time=datetime.utcnow() + timedelta(days=1),
                status='NS',
                odds_home=2.0,
                odds_draw=3.5,
                odds_away=3.8,
                odds_over_2_5=1.8,
                odds_under_2_5=2.0,
                odds_btts_yes=1.7,
                odds_btts_no=2.1
            ),
            Match(
                league_id=1,
                home_team_id=t3.id,
                away_team_id=t4.id,
                start_time=datetime.utcnow() + timedelta(days=1),
                status='NS',
                odds_home=1.5,
                odds_draw=4.0,
                odds_away=6.0,
                odds_over_2_5=1.6,
                odds_under_2_5=2.3,
                odds_btts_yes=1.9,
                odds_btts_no=1.9
            )
        ]
        
        t1_name, t2_name = t1.name, t2.name
        t3_name, t4_name = t3.name, t4.name
        
        session.add_all(matches)
        await session.commit()
        print(f"Seeded 2 upcoming matches: {t1_name} vs {t2_name}, {t3_name} vs {t4_name}")

if __name__ == "__main__":
    asyncio.run(seed_upcoming_matches())
