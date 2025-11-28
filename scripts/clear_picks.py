from app.core.database import SessionLocal
from app.core.models import DailyPick
from sqlalchemy import delete
import asyncio

async def clear_picks():
    async with SessionLocal() as session:
        await session.execute(delete(DailyPick))
        await session.commit()
        print("Cleared daily_picks table.")

if __name__ == "__main__":
    asyncio.run(clear_picks())
