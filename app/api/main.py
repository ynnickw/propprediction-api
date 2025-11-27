from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from datetime import datetime, date
from contextlib import asynccontextmanager

from ..core.database import get_db, engine, Base
from ..core.models import DailyPick, Match
from ..core.schemas import PickResponse, LeagueResponse, HealthResponse
from .auth import get_api_key
from ..services.scheduler import start_scheduler
from ..core.utils import configure_logging, get_logger
from ..data.data_ingestion import LEAGUES

configure_logging()
logger = get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting up FootProp AI Backend")
    start_scheduler()
    yield
    # Shutdown
    logger.info("Shutting down")

app = FastAPI(
    title="FootProp AI",
    description="AI-driven sports betting tool for European football player prop predictions.",
    version="0.1.0",
    lifespan=lifespan
)

@app.get("/health", response_model=HealthResponse)
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow()
    }

@app.get("/picks", response_model=List[PickResponse])
async def get_todays_picks(
    session: AsyncSession = Depends(get_db),
    api_key: str = Depends(get_api_key),
    prediction_type: Optional[str] = None
):
    """Get top value picks for today. Optionally filter by prediction_type ('player_prop', 'over_under_2.5', 'btts')."""
    today = date.today()
    stmt = select(DailyPick).where(
        DailyPick.created_at >= datetime.combine(today, datetime.min.time())
    )
    
    # Filter by prediction_type if provided
    if prediction_type:
        stmt = stmt.where(DailyPick.prediction_type == prediction_type)
    
    stmt = stmt.order_by(DailyPick.edge_percent.desc()).limit(15)
    
    result = await session.execute(stmt)
    picks = result.scalars().all()
    return picks

@app.get("/picks/{date_str}", response_model=List[PickResponse])
async def get_historical_picks(
    date_str: str,
    session: AsyncSession = Depends(get_db),
    api_key: str = Depends(get_api_key)
):
    """Get historical picks by date (YYYY-MM-DD)."""
    try:
        query_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        
    stmt = select(DailyPick).where(
        DailyPick.created_at >= datetime.combine(query_date, datetime.min.time()),
        DailyPick.created_at < datetime.combine(query_date, datetime.max.time())
    ).order_by(DailyPick.edge_percent.desc())
    
    result = await session.execute(stmt)
    picks = result.scalars().all()
    return picks

@app.get("/picks/match", response_model=List[PickResponse])
async def get_match_picks(
    session: AsyncSession = Depends(get_db),
    api_key: str = Depends(get_api_key),
    prediction_type: Optional[str] = None
):
    """Get match-level picks (Over/Under 2.5 or BTTS). Optionally filter by prediction_type."""
    today = date.today()
    stmt = select(DailyPick).where(
        DailyPick.created_at >= datetime.combine(today, datetime.min.time()),
        DailyPick.prediction_type.in_(['over_under_2.5', 'btts'])
    )
    
    # Filter by prediction_type if provided
    if prediction_type:
        stmt = stmt.where(DailyPick.prediction_type == prediction_type)
    
    stmt = stmt.order_by(DailyPick.edge_percent.desc()).limit(20)
    
    result = await session.execute(stmt)
    picks = result.scalars().all()
    return picks


@app.get("/leagues", response_model=List[LeagueResponse])
async def get_leagues():
    """List supported leagues."""
    return [{"id": id, "name": name} for name, id in LEAGUES.items()]

@app.post("/webhook/odds")
async def odds_webhook(payload: dict):
    """Optional webhook for real-time odds updates."""
    logger.info("Received odds webhook", payload=payload)
    return {"status": "received"}
