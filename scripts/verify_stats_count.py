import asyncio
import sys
import os
from sqlalchemy import text

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.infrastructure.db.session import SessionLocal

async def count_stats():
    async with SessionLocal() as session:
        result = await session.execute(text("SELECT COUNT(*) FROM historical_stats"))
        count = result.scalar()
        print(f"Total historical stats: {count}")

if __name__ == "__main__":
    asyncio.run(count_stats())
