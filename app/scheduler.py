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
        # We join with Match to ensure we have match info
        stmt = select(PropLine, Match, Player).join(Match).join(Player).where(Match.status == 'NS')
        result = await session.execute(stmt)
        # Result is rows of (PropLine, Match, Player) tuples
        rows = result.all()
        
        logger.info(f"Found {len(rows)} prop lines to process")
        
        for row in rows:
            prop = row[0]
            match = row[1]
            player = row[2]
            
            # Fetch real historical stats for the player
            # Get last 20 matches to ensure we have enough for rolling 10
            stmt_hist = select(HistoricalStat).where(
                HistoricalStat.player_id == player.id
            ).order_by(HistoricalStat.match_date.desc()).limit(20)
            
            result_hist = await session.execute(stmt_hist)
            historical_stats = result_hist.scalars().all()
            
            if not historical_stats:
                logger.warning(f"No historical stats for {player.name}, skipping prediction")
                continue
            
            # Feature Engineering
            # We pass None for team_stats and odds for now (will use defaults in features.py)
            # In a future update, we should fetch these from DB or API
            try:
                features = prepare_features(player, match, historical_stats)
            except Exception as e:
                logger.error(f"Feature engineering failed for {player.name}: {e}")
                continue
            
            # Prediction
            try:
                prediction = predict_props(features, prop.prop_type)
                expected_value = prediction['expected_value']
                model_obj = prediction['model_obj']
            except Exception as e:
                logger.error(f"Prediction failed for {player.name} {prop.prop_type}: {e}")
                continue
            
            # Edge Calculation
            if prop.odds_over > 0:
                # Calculate True Probability of Over X
                model_prob = model_obj.calculate_probability(expected_value, prop.line, 'Over')
                bookmaker_prob = 1 / prop.odds_over
                
                edge = (model_prob - bookmaker_prob) / bookmaker_prob * 100
                
                if edge >= 5.0: # Lower threshold for testing
                    logger.info(f"*** FOUND PICK *** {player.name} {prop.prop_type} {prop.line} Over | Edge: {edge:.2f}%")
                    
                    # Check if pick already exists to avoid duplicates
                    stmt_pick = select(DailyPick).where(
                        DailyPick.player_name == player.name,
                        DailyPick.match_info == f"{match.home_team} vs {match.away_team}",
                        DailyPick.prop_type == prop.prop_type,
                        DailyPick.line == prop.line,
                        DailyPick.recommendation == "Over"
                    )
                    existing_pick = (await session.execute(stmt_pick)).scalar_one_or_none()
                    
                    if not existing_pick:
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
            
            #TODO: Logic for Under (if needed, usually we focus on Over for props)
            # ...
        
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
