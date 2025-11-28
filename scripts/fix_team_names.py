import asyncio
import sys
import os
from sqlalchemy import select, update, text

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal
from app.core.models import Match, Player, HistoricalStat

async def fix_team_names():
    async with SessionLocal() as session:
        print("Fixing team names...")
        
        # Define mappings (Incorrect -> Correct)
        mappings = {
            'Borussia Monchengladbach': 'Borussia Mönchengladbach',
            'Bayern Munchen': 'Bayern München',
            '1. FC Koln': '1.FC Köln',
            '1. FC Köln': '1.FC Köln', # Ensure consistency
            'Bayer 04 Leverkusen': 'Bayer Leverkusen',
            'Mainz 05': 'FSV Mainz 05',
            'Hertha BSC': 'Hertha Berlin',
            'SpVgg Greuther Furth': 'Greuther Fürth',
            'VfL Bochum 1848': 'VfL Bochum',
            'Schalke 04': 'FC Schalke 04',
            'Arminia Bielefeld': 'DSC Arminia Bielefeld'
        }
        
        for incorrect, correct in mappings.items():
            print(f"Updating '{incorrect}' to '{correct}'...")
            
            # Update Matches (Home)
            stmt = update(Match).where(Match.home_team == incorrect).values(home_team=correct)
            result = await session.execute(stmt)
            if result.rowcount > 0:
                print(f"  Updated {result.rowcount} matches (home)")
                
            # Update Matches (Away)
            stmt = update(Match).where(Match.away_team == incorrect).values(away_team=correct)
            result = await session.execute(stmt)
            if result.rowcount > 0:
                print(f"  Updated {result.rowcount} matches (away)")
                
            # Update Players
            stmt = update(Player).where(Player.team == incorrect).values(team=correct)
            result = await session.execute(stmt)
            if result.rowcount > 0:
                print(f"  Updated {result.rowcount} players")
                
            # Update Historical Stats (Opponent)
            stmt = update(HistoricalStat).where(HistoricalStat.opponent == incorrect).values(opponent=correct)
            result = await session.execute(stmt)
            if result.rowcount > 0:
                print(f"  Updated {result.rowcount} historical stats")
        
        await session.commit()
        print("Team name standardization complete.")

if __name__ == "__main__":
    asyncio.run(fix_team_names())
