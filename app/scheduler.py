from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from .data_ingestion import run_ingestion
from .database import SessionLocal
from .models import Match, Player, PropLine, DailyPick, HistoricalStat
from .features import prepare_features
from .model import predict_props
from sqlalchemy import select, func, desc
import structlog
import asyncio

logger = structlog.get_logger()

scheduler = AsyncIOScheduler()

async def get_team_stats(session, team_name):
    """
    Fetch recent team stats (shots, conceded) from historical data.
    For now, returning defaults to keep it fast, but this is where 
    you'd aggregate HistoricalStat data.
    """
    # 1. Team Shots (Last 5 matches)
    # Subquery to get total shots per match for this team
    stmt_shots = (
        select(
            HistoricalStat.match_date,
            func.sum(HistoricalStat.shots).label("total_shots")
        )
        .join(Player)
        .where(Player.team == team_name)
        .group_by(HistoricalStat.match_date)
        .order_by(desc(HistoricalStat.match_date))
        .limit(5)
    )
    
    result_shots = await session.execute(stmt_shots)
    shots_per_match = [row.total_shots for row in result_shots]
    
    avg_shots = sum(shots_per_match) / len(shots_per_match) if shots_per_match else 12.0

    # 2. Conceded Shots (Last 5 matches)
    # Sum of shots by opponents against this team
    stmt_conceded = (
        select(
            HistoricalStat.match_date,
            func.sum(HistoricalStat.shots).label("total_conceded")
        )
        .where(HistoricalStat.opponent == team_name)
        .group_by(HistoricalStat.match_date)
        .order_by(desc(HistoricalStat.match_date))
        .limit(5)
    )
    
    result_conceded = await session.execute(stmt_conceded)
    conceded_per_match = [row.total_conceded for row in result_conceded]
    
    avg_conceded = sum(conceded_per_match) / len(conceded_per_match) if conceded_per_match else 12.0
    
    return {
        'team_shots_avg': float(avg_shots),
        'opp_conceded_shots_avg': float(avg_conceded)
    }

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
        
        # Cache team stats to avoid re-fetching
        team_stats_cache = {}
        
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
            
            # Filter: Must have played in at least 5 of the last 10 games
            last_10_games = historical_stats[:10]
            games_played = sum(1 for game in last_10_games if game.minutes_played > 0)
            
            if games_played < 5:
                # logger.info(f"Skipping {player.name}: Played only {games_played}/10 recent games")
                continue
            
            # Prepare Team Stats
            if player.team not in team_stats_cache:
                team_stats_cache[player.team] = await get_team_stats(session, player.team)
            
            # Prepare Odds
            # Use odds from Match table, default to 2.5 if missing
            match_odds = {
                'B365H': match.odds_home if match.odds_home else 2.5,
                'B365D': match.odds_draw if match.odds_draw else 3.2,
                'B365A': match.odds_away if match.odds_away else 2.5
            }
            
            # Feature Engineering
            try:
                features = prepare_features(
                    player, 
                    match, 
                    historical_stats, 
                    team_stats=team_stats_cache[player.team], 
                    odds=match_odds
                )
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
            
            # Edge Calculation (Over)
            if prop.odds_over > 0:
                # Calculate True Probability of Over X
                model_prob_over = model_obj.calculate_probability(expected_value, prop.line, 'Over')
                bookmaker_prob_over = 1 / prop.odds_over
                
                edge_over = (model_prob_over - bookmaker_prob_over) / bookmaker_prob_over * 100
                
                # Debug logging
                logger.info(f"DEBUG: {player.name} {prop.prop_type} {prop.line} | Exp: {expected_value:.2f} | ModelProbOver: {model_prob_over:.2f} | EdgeOver: {edge_over:.2f}%")
                
                if edge_over >= 1.0: 
                    logger.info(f"*** FOUND PICK *** {player.name} {prop.prop_type} {prop.line} Over | Edge: {edge_over:.2f}%")
                    
                    # Store Pick (Over)
                    # Store Pick (Over)
                    stmt_pick = select(DailyPick).where(
                        DailyPick.player_id == player.id,
                        DailyPick.match_id == match.id,
                        DailyPick.prop_type == prop.prop_type,
                        DailyPick.line == prop.line,
                        DailyPick.recommendation == "Over"
                    )
                    existing_pick = (await session.execute(stmt_pick)).scalar_one_or_none()
                    
                    if not existing_pick:
                        pick = DailyPick(
                            player_id=player.id,
                            match_id=match.id,
                            prop_type=prop.prop_type,
                            line=prop.line,
                            recommendation="Over",
                            model_expected=expected_value,
                            bookmaker_prob=bookmaker_prob_over,
                            model_prob=model_prob_over,
                            edge_percent=edge_over,
                            confidence="High" if edge_over > 15 else "Medium"
                        )
                        session.add(pick)

            # Edge Calculation (Under)
            # If odds_under is 0, try to infer from odds_over
            odds_under = prop.odds_under
            if odds_under == 0 and prop.odds_over > 0:
                # Infer Under odds with VIG/Margin adjustment
                # Bookmakers usually have a margin (e.g., 1.07 to 1.10 sum of probs)
                # P_Over_Implied + P_Under_Implied = 1.07 (assuming 7% vig)
                
                prob_over_implied = 1 / prop.odds_over
                target_market_sum = 1.07 # Standard vig
                
                # If Over is extremely likely (e.g. 1.01 -> 0.99), P_Under would be 1.07 - 0.99 = 0.08
                # This results in Odds ~ 12.5, which is more realistic than 100.0
                
                if prob_over_implied < target_market_sum:
                    prob_under_implied = target_market_sum - prob_over_implied
                    
                    # Safety check: ensure probability is valid (0 < p < 1)
                    if 0 < prob_under_implied < 1:
                        odds_under = 1 / prob_under_implied
                    else:
                        odds_under = 0 # Cannot infer valid odds
            
            if odds_under > 0:
                # Calculate True Probability of Under X
                model_prob_under = model_obj.calculate_probability(expected_value, prop.line, 'Under')
                bookmaker_prob_under = 1 / odds_under
                
                edge_under = (model_prob_under - bookmaker_prob_under) / bookmaker_prob_under * 100
                
                # Debug logging
                logger.info(f"DEBUG: {player.name} {prop.prop_type} {prop.line} | Exp: {expected_value:.2f} | ModelProbUnder: {model_prob_under:.2f} | ImpliedOdds: {odds_under:.2f} | EdgeUnder: {edge_under:.2f}%")
                
                # Higher threshold for Under bets (10.0%) to reduce noise
                if edge_under >= 10.0:
                    logger.info(f"*** FOUND PICK *** {player.name} {prop.prop_type} {prop.line} Under | Edge: {edge_under:.2f}%")
                    
                    # Store Pick (Under)
                    stmt_pick = select(DailyPick).where(
                        DailyPick.player_id == player.id,
                        DailyPick.match_id == match.id,
                        DailyPick.prop_type == prop.prop_type,
                        DailyPick.line == prop.line,
                        DailyPick.recommendation == "Under"
                    )
                    existing_pick = (await session.execute(stmt_pick)).scalar_one_or_none()
                    
                    if not existing_pick:
                        pick = DailyPick(
                            player_id=player.id,
                            match_id=match.id,
                            prop_type=prop.prop_type,
                            line=prop.line,
                            recommendation="Under",
                            model_expected=expected_value,
                            bookmaker_prob=bookmaker_prob_under,
                            model_prob=model_prob_under,
                            edge_percent=edge_under,
                            confidence="High" if edge_under > 15 else "Medium"
                        )
                        session.add(pick)
        
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

if __name__ == "__main__":
    # Allow running the pipeline manually for testing
    asyncio.run(pipeline_job())
