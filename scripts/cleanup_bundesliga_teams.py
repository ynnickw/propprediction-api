import asyncio
import sys
import os
from sqlalchemy import select, update, delete

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.infrastructure.db.session import SessionLocal
from app.domain.models import Team, Match

# Mapping of duplicate team names to canonical names
# Format: "duplicate_name": "canonical_name"
TEAM_MERGES = {
    "Augsburg": "FC Augsburg",
    "Dortmund": "Borussia Dortmund",
    "Ein Frankfurt": "Eintracht Frankfurt",
    "Freiburg": "SC Freiburg",
    "Hamburg": "Hamburger SV",
    "Hoffenheim": "1899 Hoffenheim",
    "Leverkusen": "Bayer Leverkusen",
    "M'gladbach": "Borussia Mönchengladbach",
    "St Pauli": "FC St. Pauli",
    "Stuttgart": "VfB Stuttgart",
    "Wolfsburg": "VfL Wolfsburg",
}

async def cleanup_bundesliga_teams():
    """Merge all duplicate Bundesliga teams into canonical names."""
    async with SessionLocal() as session:
        total_merged = 0
        total_matches_updated = 0
        
        for duplicate_name, canonical_name in TEAM_MERGES.items():
            # Find the duplicate team
            stmt = select(Team).where(
                Team.name == duplicate_name,
                Team.league == "Bundesliga"
            )
            result = await session.execute(stmt)
            duplicate_team = result.scalar_one_or_none()
            
            if not duplicate_team:
                print(f"⚠️  Duplicate team '{duplicate_name}' not found, skipping")
                continue
            
            # Find the canonical team
            stmt = select(Team).where(
                Team.name == canonical_name,
                Team.league == "Bundesliga"
            )
            result = await session.execute(stmt)
            canonical_team = result.scalar_one_or_none()
            
            if not canonical_team:
                print(f"⚠️  Canonical team '{canonical_name}' not found for '{duplicate_name}'")
                print(f"   Renaming '{duplicate_name}' to '{canonical_name}'")
                stmt = (
                    update(Team)
                    .where(Team.id == duplicate_team.id)
                    .values(name=canonical_name)
                )
                await session.execute(stmt)
                total_merged += 1
                continue
            
            print(f"\n✓ Merging '{duplicate_name}' (ID: {duplicate_team.id}) -> '{canonical_name}' (ID: {canonical_team.id})")
            
            # Update all matches using the duplicate team
            # Update home_team_id
            stmt = (
                update(Match)
                .where(Match.home_team_id == duplicate_team.id)
                .values(home_team_id=canonical_team.id)
            )
            result = await session.execute(stmt)
            home_count = result.rowcount
            print(f"  Updated {home_count} matches (home_team_id)")
            total_matches_updated += home_count
            
            # Update away_team_id
            stmt = (
                update(Match)
                .where(Match.away_team_id == duplicate_team.id)
                .values(away_team_id=canonical_team.id)
            )
            result = await session.execute(stmt)
            away_count = result.rowcount
            print(f"  Updated {away_count} matches (away_team_id)")
            total_matches_updated += away_count
            
            # Delete the duplicate team
            stmt = delete(Team).where(Team.id == duplicate_team.id)
            await session.execute(stmt)
            print(f"  Deleted duplicate team '{duplicate_name}'")
            total_merged += 1
        
        await session.commit()
        
        print(f"\n{'='*60}")
        print(f"✅ Cleanup Complete!")
        print(f"   Teams merged: {total_merged}")
        print(f"   Matches updated: {total_matches_updated}")
        print(f"{'='*60}")

if __name__ == "__main__":
    asyncio.run(cleanup_bundesliga_teams())
