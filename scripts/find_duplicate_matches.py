import asyncio
import sys
import os
from sqlalchemy import select, func, and_
from sqlalchemy.orm import joinedload

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.infrastructure.db.session import SessionLocal
from app.domain.models import Match

async def find_duplicate_matches():
    """Find duplicate matches based on home_team_id, away_team_id, and date."""
    async with SessionLocal() as session:
        # Find matches with the same teams and date
        stmt = (
            select(
                Match.home_team_id,
                Match.away_team_id,
                func.date(Match.start_time).label('match_date'),
                func.count(Match.id).label('count')
            )
            .group_by(
                Match.home_team_id,
                Match.away_team_id,
                func.date(Match.start_time)
            )
            .having(func.count(Match.id) > 1)
        )
        
        result = await session.execute(stmt)
        duplicates = result.all()
        
        if not duplicates:
            print("✓ No duplicate matches found!")
            return
        
        print(f"⚠️  Found {len(duplicates)} sets of duplicate matches:\n")
        
        total_duplicates = 0
        for home_id, away_id, match_date, count in duplicates:
            # Get the actual matches
            stmt = select(Match).where(
                and_(
                    Match.home_team_id == home_id,
                    Match.away_team_id == away_id,
                    func.date(Match.start_time) == match_date
                )
            ).options(
                joinedload(Match.home_team_obj),
                joinedload(Match.away_team_obj)
            )
            
            result = await session.execute(stmt)
            matches = result.scalars().all()
            
            if matches:
                first_match = matches[0]
                print(f"{first_match.home_team} vs {first_match.away_team} on {match_date}")
                print(f"  {count} duplicates:")
                for match in matches:
                    print(f"    ID: {match.id}, Status: {match.status}, Fixture ID: {match.fixture_id}, Scores: {match.home_score}-{match.away_score}")
                print()
                total_duplicates += count - 1
        
        print(f"Total duplicate matches to clean up: {total_duplicates}")

if __name__ == "__main__":
    asyncio.run(find_duplicate_matches())
