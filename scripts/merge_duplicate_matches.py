import asyncio
import sys
import os
from sqlalchemy import select, func, and_, delete
from sqlalchemy.orm import joinedload

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.infrastructure.db.session import SessionLocal
from app.domain.models import Match, DailyPick

async def merge_duplicate_matches():
    """Merge duplicate matches, keeping historical scores and API-Football fixture_id."""
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
        
        print(f"⚠️  Found {len(duplicates)} sets of duplicate matches\n")
        
        total_merged = 0
        total_picks_updated = 0
        
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
            
            if len(matches) < 2:
                continue
            
            # Find the match with fixture_id (from API-Football)
            # and the match with scores (from historical data)
            api_match = None
            historical_match = None
            
            for match in matches:
                if match.fixture_id and not match.home_score:
                    api_match = match
                elif not match.fixture_id and match.home_score is not None:
                    historical_match = match
            
            if not api_match or not historical_match:
                # Try to find best candidates
                for match in matches:
                    if match.fixture_id:
                        api_match = match
                    if match.home_score is not None:
                        historical_match = match
            
            if not api_match or not historical_match or api_match.id == historical_match.id:
                print(f"⚠️  Skipping {matches[0].home_team} vs {matches[0].away_team} - cannot determine which to merge")
                continue
            
            print(f"✓ Merging {api_match.home_team} vs {api_match.away_team} on {match_date}")
            print(f"  API Match (ID: {api_match.id}, Fixture: {api_match.fixture_id})")
            print(f"  Historical Match (ID: {historical_match.id}, Score: {historical_match.home_score}-{historical_match.away_score})")
            
            # Update API match with historical data
            api_match.home_score = historical_match.home_score
            api_match.away_score = historical_match.away_score
            api_match.home_half_time_goals = historical_match.home_half_time_goals
            api_match.away_half_time_goals = historical_match.away_half_time_goals
            api_match.home_shots = historical_match.home_shots
            api_match.away_shots = historical_match.away_shots
            api_match.home_shots_on_target = historical_match.home_shots_on_target
            api_match.away_shots_on_target = historical_match.away_shots_on_target
            api_match.home_corners = historical_match.home_corners
            api_match.away_corners = historical_match.away_corners
            api_match.home_fouls = historical_match.home_fouls
            api_match.away_fouls = historical_match.away_fouls
            api_match.home_yellow_cards = historical_match.home_yellow_cards
            api_match.away_yellow_cards = historical_match.away_yellow_cards
            api_match.home_red_cards = historical_match.home_red_cards
            api_match.away_red_cards = historical_match.away_red_cards
            api_match.odds_over_2_5 = historical_match.odds_over_2_5 or api_match.odds_over_2_5
            api_match.odds_under_2_5 = historical_match.odds_under_2_5 or api_match.odds_under_2_5
            api_match.odds_btts_yes = historical_match.odds_btts_yes or api_match.odds_btts_yes
            api_match.odds_btts_no = historical_match.odds_btts_no or api_match.odds_btts_no
            
            # Update any DailyPicks that reference the historical match
            from sqlalchemy import update
            stmt = (
                update(DailyPick)
                .where(DailyPick.match_id == historical_match.id)
                .values(match_id=api_match.id)
            )
            result = await session.execute(stmt)
            picks_updated = result.rowcount
            if picks_updated > 0:
                print(f"  Updated {picks_updated} daily picks")
                total_picks_updated += picks_updated
            
            # Delete the historical match
            await session.delete(historical_match)
            print(f"  Deleted historical match (ID: {historical_match.id})")
            
            total_merged += 1
        
        await session.commit()
        
        print(f"\n{'='*60}")
        print(f"✅ Merge Complete!")
        print(f"   Duplicate sets merged: {total_merged}")
        print(f"   Daily picks updated: {total_picks_updated}")
        print(f"{'='*60}")

if __name__ == "__main__":
    asyncio.run(merge_duplicate_matches())
