from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from .data_ingestion import run_ingestion
from .database import SessionLocal
from .models import Match, Player, PropLine, DailyPick
from .features import prepare_features
from .model import predict_props
from sqlalchemy import select
import structlog
import asyncio

logger = structlog.get_logger()

scheduler = AsyncIOScheduler()

async def pipeline_job():
    logger.info("Starting pipeline job")
    
    # 1. Ingest Data
    await run_ingestion()
    
    # 2. Run Predictions
    async with SessionLocal() as session:
        # Fetch upcoming matches and props
        stmt = select(PropLine).join(Match).where(Match.status == 'NS') # Not Started
        result = await session.execute(stmt)
        prop_lines = result.scalars().all()
        
        for prop in prop_lines:
            # Fetch related data
            player = await session.get(Player, prop.player_id)
            match = await session.get(Match, prop.match_id)
            
            # Fetch real historical stats (assuming they are populated now)
            # In a real run, you'd query the HistoricalStat table
            historical_stats = [] 
            
            # Feature Engineering
            features = prepare_features(player, match, historical_stats)
            
            # Prediction
            prediction = predict_props(features, prop.prop_type)
            expected_value = prediction['expected_value']
            model_obj = prediction['model_obj']
            
            # Edge Calculation
            # We need to calculate the probability of the SPECIFIC line offered
            # e.g. Bookmaker offers Over 3.5 @ 1.85
            
            if prop.odds_over > 0:
                # Calculate True Probability of Over X
                model_prob = model_obj.calculate_probability(expected_value, prop.line, 'Over')
                bookmaker_prob = 1 / prop.odds_over
                
                edge = (model_prob - bookmaker_prob) / bookmaker_prob * 100
                
                # logger.info(f"Prop: {player.name} {prop.prop_type} {prop.line} | EV: {expected_value:.2f} | Model Prob: {model_prob:.2f} | Bookie Prob: {bookmaker_prob:.2f} | Edge: {edge:.2f}%")

                if edge >= 8.0:
                    logger.info(f"*** FOUND PICK *** {player.name} {prop.prop_type} {prop.line} Over | Edge: {edge:.2f}%")
                    pick = DailyPick(
                        player_name=player.name,
                        match_info=f"{match.home_team} vs {match.away_team}",
                        prop_type=prop.prop_type,
                        line=prop.line,
                        recommendation="Over",
                        model_expected=expected_value,
                        bookmaker_prob=bookmaker_prob,
                        model_prob=model_prob,
                        edge_percent=edge,
                        confidence="High" if edge > 15 else "Medium"
                    )
                    session.add(pick)
            
            # Similar logic for Under...
        
        await session.commit()
    
    logger.info("Pipeline job completed")

def start_scheduler():
    scheduler.add_job(
        pipeline_job,
        trigger=IntervalTrigger(hours=6),
        id="pipeline_job",
        replace_existing=True
    )
    scheduler.start()
