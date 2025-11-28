from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from app.services.data_service import DataService
from app.services.prediction_service import PredictionService
from app.infrastructure.db.session import SessionLocal
import structlog
import asyncio

logger = structlog.get_logger()

scheduler = AsyncIOScheduler()

async def pipeline_job():
    logger.info("Starting pipeline job")
    
    async with SessionLocal() as session:
        # 1. Ingest Data
        data_service = DataService(session)
        await data_service.fetch_upcoming_matches()
        await data_service.fetch_match_odds()
        
        # 2. Run Predictions
        prediction_service = PredictionService(session)
        await prediction_service.generate_player_prop_predictions()
        await prediction_service.generate_match_predictions()

def start_scheduler():
    scheduler.add_job(
        pipeline_job,
        trigger=IntervalTrigger(hours=6),
        id="pipeline_job",
        replace_existing=True
    )
    scheduler.start()

if __name__ == "__main__":
    # Allow running the pipeline manually for testing
    asyncio.run(pipeline_job())
