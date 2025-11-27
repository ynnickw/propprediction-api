import asyncio
from ..core.database import engine, Base
from ..core.models import Match, Player, PropLine, HistoricalStat, DailyPick, User

async def init_models():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Database tables created successfully.")

if __name__ == "__main__":
    asyncio.run(init_models())
