import structlog
import pandas as pd
import time
from sqlalchemy import select, func, desc
from datetime import datetime
from sqlalchemy.orm import joinedload
from app.domain.models import Match, Player, PropLine, DailyPick, HistoricalStat
from app.ml.predictor import predict_props, predict_match_outcome
from app.ml.utils import calculate_edge
from app.features.pipeline import (
    prepare_match_features_for_prediction, 
    engineer_over_under_2_5_features, 
    engineer_btts_features
)
from app.features.data_loader import load_match_level_data
from app.ml.features import prepare_features

logger = structlog.get_logger()

class PredictionService:
    def __init__(self, session):
        self.session = session
        self.team_stats_cache = {}

    async def get_team_stats(self, team_name):
        """
        Fetch recent team stats (shots, conceded) from historical data.
        """
        if team_name in self.team_stats_cache:
            return self.team_stats_cache[team_name]

        # 1. Team Shots (Last 5 matches)
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
        
        result_shots = await self.session.execute(stmt_shots)
        shots_per_match = [row.total_shots for row in result_shots]
        
        avg_shots = sum(shots_per_match) / len(shots_per_match) if shots_per_match else 12.0

        # 2. Conceded Shots (Last 5 matches)
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
        
        result_conceded = await self.session.execute(stmt_conceded)
        conceded_per_match = [row.total_conceded for row in result_conceded]
        
        avg_conceded = sum(conceded_per_match) / len(conceded_per_match) if conceded_per_match else 12.0
        
        stats = {
            'team_shots_avg': float(avg_shots),
            'opp_conceded_shots_avg': float(avg_conceded)
        }
        self.team_stats_cache[team_name] = stats
        return stats

    async def generate_player_prop_predictions(self):
        """
        Generate predictions for player props.
        """
        logger.info("Generating player prop predictions")
        
        # Fetch upcoming matches and props
        stmt = select(PropLine, Match, Player).join(Match).join(Player).options(
            joinedload(Match.home_team_obj),
            joinedload(Match.away_team_obj)
        ).where(Match.status == 'NS')
        result = await self.session.execute(stmt)
        rows = result.all()
        
        logger.info(f"Found {len(rows)} prop lines to process")
        
        for row in rows:
            prop = row[0]
            match = row[1]
            player = row[2]
            
            # Fetch real historical stats for the player
            stmt_hist = select(HistoricalStat).where(
                HistoricalStat.player_id == player.id
            ).order_by(HistoricalStat.match_date.desc()).limit(20)
            
            result_hist = await self.session.execute(stmt_hist)
            historical_stats = result_hist.scalars().all()
            
            if not historical_stats:
                continue
            
            # Filter 1: Must have played in at least 5 of the last 10 games
            last_10_games = historical_stats[:10]
            games_played = sum(1 for game in last_10_games if game.minutes_played > 0)
            
            if games_played < 5:
                continue
            
            # Filter 2: Must have averaged > 45 minutes in games played
            total_minutes = sum(game.minutes_played for game in last_10_games)
            avg_minutes = total_minutes / len(last_10_games) if last_10_games else 0
            
            if avg_minutes <= 45:
                continue
            
            # Prepare Team Stats
            team_stats = await self.get_team_stats(player.team)
            
            # Prepare Odds
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
                    team_stats=team_stats, 
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
                model_prob_over = model_obj.calculate_probability(expected_value, prop.line, 'Over')
                bookmaker_prob_over, edge_over = calculate_edge(model_prob_over, prop.odds_over)
                
                if edge_over >= 1.0: 
                    logger.info(f"*** FOUND PICK *** {player.name} {prop.prop_type} {prop.line} Over | Edge: {edge_over:.2f}%")
                    await self._store_pick(player.id, match.id, prop.prop_type, prop.line, "Over", 
                                         expected_value, bookmaker_prob_over, model_prob_over, edge_over)

            # Edge Calculation (Under)
            if prop.odds_over > 0 and prop.odds_over < 1.2:
                continue
            
            odds_under = prop.odds_under
            if odds_under == 0 and prop.odds_over > 0:
                prob_over_implied = 1 / prop.odds_over
                target_market_sum = 1.07
                if prob_over_implied < target_market_sum:
                    prob_under_implied = target_market_sum - prob_over_implied
                    if 0 < prob_under_implied < 1:
                        odds_under = 1 / prob_under_implied
            
            if odds_under > 0:
                model_prob_under = model_obj.calculate_probability(expected_value, prop.line, 'Under')
                bookmaker_prob_under, edge_under = calculate_edge(model_prob_under, odds_under)
                
                if edge_under >= 10.0:
                    logger.info(f"*** FOUND PICK *** {player.name} {prop.prop_type} {prop.line} Under | Edge: {edge_under:.2f}%")
                    await self._store_pick(player.id, match.id, prop.prop_type, prop.line, "Under", 
                                         expected_value, bookmaker_prob_under, model_prob_under, edge_under)
        
        await self.session.commit()


    async def generate_match_predictions(self):
        """
        Generate match-level predictions (Over/Under 2.5 and BTTS) for upcoming matches.
        """
        start_time = time.time()
        logger.info("Generating match-level predictions")
        
        # Fetch upcoming matches with odds
        stmt = select(Match).options(
            joinedload(Match.home_team_obj),
            joinedload(Match.away_team_obj)
        ).where(
            Match.status == 'NS'  # Not started
        )
        result = await self.session.execute(stmt)
        matches = result.scalars().all()
        
        if not matches:
            logger.info("No upcoming matches found for prediction")
            return
        
        logger.info(f"Found {len(matches)} upcoming matches")
        
        # Load historical match data for feature engineering
        try:
            historical_df = load_match_level_data()
            historical_df = engineer_over_under_2_5_features(historical_df)
            historical_df_btts = engineer_btts_features(historical_df)
        except Exception as e:
            logger.warning(f"Could not load historical match data: {e}")
            historical_df = None
            historical_df_btts = None
        
        predictions = []
        
        for match in matches:
            # Skip if no odds available
            if not match.odds_over_2_5 and not match.odds_btts_yes:
                logger.debug(f"Skipping match {match.home_team} vs {match.away_team}: No odds available")
                continue
            
            try:
                # Prepare features
                features_over_under, features_btts = prepare_match_features_for_prediction(
                    match, historical_df if historical_df is not None else None
                )
                
                # Over/Under 2.5 prediction
                if match.odds_over_2_5:
                    try:
                        # Get feature columns (exclude metadata and raw stats to match training)
                        exclude_cols = ['date', 'Date', 'Div', 'Time', 'HomeTeam', 'AwayTeam', 
                                        'FTHG', 'FTAG', 'FTR', 'HTHG', 'HTAG', 'HTR',
                                        'home_team', 'away_team', 'home_score', 'away_score',
                                        'home_half_time_goals', 'away_half_time_goals',
                                        'home_shots', 'away_shots', 'home_shots_on_target', 'away_shots_on_target',
                                        'home_corners', 'away_corners', 'home_fouls', 'away_fouls',
                                        'home_yellow_cards', 'away_yellow_cards', 'home_red_cards', 'away_red_cards',
                                        'odds_home', 'odds_draw', 'odds_away', 'odds_over_2_5', 'odds_under_2_5',
                                        'odds_btts_yes', 'odds_btts_no',
                                        'total_goals', 'over_2_5', 'btts', 'year']
                        feature_cols = [col for col in features_over_under.columns 
                                       if col not in exclude_cols and pd.api.types.is_numeric_dtype(features_over_under[col])]
                        
                        if len(feature_cols) > 0:
                            pred_result = predict_match_outcome(features_over_under[feature_cols], 'over_under_2.5')
                            model_prob = pred_result['model_prob']
                            recommendation = pred_result['recommendation']
                            expected_value = pred_result.get('expected_value', 0.0)
                            
                            # Calculate edge
                            if recommendation == 'Over' and match.odds_over_2_5:
                                bookmaker_prob, edge = calculate_edge(model_prob, match.odds_over_2_5)
                            elif recommendation == 'Under' and match.odds_under_2_5:
                                bookmaker_prob, edge = calculate_edge(1 - model_prob, match.odds_under_2_5)
                            else:
                                edge = 0.0
                                bookmaker_prob = 0.0
                            
                            if edge >= 8.0:  # Minimum edge threshold
                                predictions.append({
                                    'match': match,
                                    'prediction_type': 'over_under_2.5',
                                    'recommendation': recommendation,
                                    'model_prob': (1 - model_prob) if recommendation == 'Under' else model_prob,
                                    'expected_value': expected_value,
                                    'bookmaker_prob': bookmaker_prob,
                                    'edge_percent': edge,
                                    'odds': match.odds_over_2_5 if recommendation == 'Over' else match.odds_under_2_5
                                })
                    except Exception as e:
                        logger.error(f"Error predicting Over/Under 2.5 for {match.home_team} vs {match.away_team}: {e}")
                
                # BTTS prediction
                if match.odds_btts_yes:
                    try:
                        # Explicitly select features used in training (21 features)
                        btts_features_list = [
                            'home_scoring_rate_season', 'home_scoring_rate_last_5', 'home_goals_avg_last_5', 
                            'home_goals_avg_season', 'home_scoreless_rate', 'home_conceding_rate_season', 
                            'home_conceding_rate_last_5', 'home_clean_sheet_rate', 'away_scoring_rate_season', 
                            'away_scoring_rate_last_5', 'away_goals_avg_last_5', 'away_goals_avg_season', 
                            'away_scoreless_rate', 'away_conceding_rate_season', 'away_conceding_rate_last_5', 
                            'away_clean_sheet_rate', 'h2h_btts_rate', 'combined_scoring_probability', 
                            'defensive_weakness_indicator', 'home_scoring_vs_away_conceding', 
                            'away_scoring_vs_home_conceding'
                        ]
                        
                        # Ensure all features exist
                        missing_cols = [col for col in btts_features_list if col not in features_btts.columns]
                        if missing_cols:
                            logger.warning(f"Missing BTTS features: {missing_cols}")
                            continue
                            
                        feature_cols = btts_features_list
                        
                        if len(feature_cols) > 0:
                            pred_result = predict_match_outcome(features_btts[feature_cols], 'btts')
                            model_prob = pred_result['model_prob']
                            recommendation = pred_result['recommendation']
                            expected_value = pred_result.get('expected_value', 0.0)
                            
                            # Calculate edge
                            if recommendation == 'Yes' and match.odds_btts_yes:
                                bookmaker_prob, edge = calculate_edge(model_prob, match.odds_btts_yes)
                                odds = match.odds_btts_yes
                            elif recommendation == 'No' and match.odds_btts_no:
                                bookmaker_prob, edge = calculate_edge(1 - model_prob, match.odds_btts_no)
                                odds = match.odds_btts_no
                            else:
                                edge = 0.0
                                bookmaker_prob = 0.0
                                odds = None
                            
                            if edge >= 8.0 and odds:
                                predictions.append({
                                    'match': match,
                                    'prediction_type': 'btts',
                                    'recommendation': recommendation,
                                    'model_prob': (1 - model_prob) if recommendation == 'No' else model_prob,
                                    'expected_value': expected_value,
                                    'bookmaker_prob': bookmaker_prob,
                                    'edge_percent': edge,
                                    'odds': odds
                                })
                    except Exception as e:
                        logger.error(f"Error predicting BTTS for {match.home_team} vs {match.away_team}: {e}")
            
            except Exception as e:
                logger.error(f"Error processing match {match.home_team} vs {match.away_team}: {e}")
                continue
        
        # Store picks in database
        for pred in predictions:
            try:
                await self._store_pick(
                    player_id=None,
                    match_id=pred['match'].id,
                    prop_type=pred['prediction_type'],
                    line=2.5 if pred['prediction_type'] == 'over_under_2.5' else None,
                    recommendation=pred['recommendation'],
                    expected_value=pred.get('expected_value', 0.0),
                    bookmaker_prob=pred['bookmaker_prob'],
                    model_prob=pred['model_prob'],
                    edge=pred['edge_percent'],
                    prediction_type=pred['prediction_type']
                )
                logger.info(f"Created match pick: {pred['match'].home_team} vs {pred['match'].away_team} - {pred['prediction_type']} {pred['recommendation']} (Edge: {pred['edge_percent']:.2f}%)")
            except Exception as e:
                logger.error(f"Error storing pick: {e}")
        
        await self.session.commit()
        
        elapsed_time = time.time() - start_time
        logger.info(f"Generated {len(predictions)} match-level picks in {elapsed_time:.2f} seconds")
        
        # Log performance metrics
        if matches:
            logger.info(f"Processed {len(matches)} matches, {len(predictions)} picks generated ({len(predictions)/len(matches)*100:.1f}% pick rate)")

    async def _store_pick(self, player_id, match_id, prop_type, line, recommendation, expected_value, bookmaker_prob, model_prob, edge, prediction_type='player_prop'):
        """Helper to store a pick. Updates existing pick if found, otherwise creates new."""
        # Check for existing pick for this specific market (player/match/prop/line)
        # We don't include recommendation in the check because we want to overwrite 
        # if the recommendation changes (e.g. from Over to Under)
        stmt = select(DailyPick).where(
            DailyPick.player_id == player_id,
            DailyPick.match_id == match_id,
            DailyPick.prop_type == prop_type,
            DailyPick.line == line
        )
        existing_pick = (await self.session.execute(stmt)).scalar_one_or_none()
        
        if existing_pick:
            # Update existing pick
            existing_pick.recommendation = recommendation
            existing_pick.model_expected = expected_value
            existing_pick.bookmaker_prob = bookmaker_prob
            existing_pick.model_prob = model_prob
            existing_pick.edge_percent = edge
            existing_pick.confidence = "High" if edge > 15 else "Medium"
            existing_pick.prediction_type = prediction_type
            existing_pick.created_at = datetime.utcnow()
            # No need to add to session, it's already attached
        else:
            # Create new pick
            pick = DailyPick(
                player_id=player_id,
                match_id=match_id,
                prediction_type=prediction_type,
                prop_type=prop_type,
                line=line,
                recommendation=recommendation,
                model_expected=expected_value,
                bookmaker_prob=bookmaker_prob,
                model_prob=model_prob,
                edge_percent=edge,
                confidence="High" if edge > 15 else "Medium",
                created_at=datetime.utcnow()
            )
            self.session.add(pick)
