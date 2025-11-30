import asyncio
import sys
import os
from sqlalchemy import delete
from sqlalchemy.future import select

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.infrastructure.db.session import SessionLocal
from app.domain.models import Match

async def cleanup_matches():
    async with SessionLocal() as session:
        # Delete all upcoming matches (NS) so they can be re-fetched with correct Team IDs
        stmt = delete(Match).where(Match.status == 'NS')
        result = await session.execute(stmt)
        # Correct usage:
        result = await session.execute(stmt)
        await session.commit()
        
        print(f"Deleted {result.rowcount} upcoming matches.")

if __name__ == "__main__":
    asyncio.run(cleanup_matches())
