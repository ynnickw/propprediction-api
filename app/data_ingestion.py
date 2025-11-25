import httpx
import os
import asyncio
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from .models import Match, Player, PropLine, HistoricalStat
from .database import SessionLocal
import structlog

logger = structlog.get_logger()

API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY")
THE_ODDS_API_KEY = os.getenv("THE_ODDS_API_KEY")

API_FOOTBALL_BASE = "https://v3.football.api-sports.io"
THE_ODDS_API_BASE = "https://api.the-odds-api.com/v4/sports"

# League IDs mapping (API Football)
LEAGUES = {
    "Bundesliga": 78,
}

# The Odds API Sport Keys
SPORT_KEYS = {
    "Bundesliga": "soccer_germany_bundesliga"
}

async def fetch_upcoming_matches(session: AsyncSession):
    """Fetch matches for the next 48 hours."""
    logger.info("Fetching upcoming matches")
    headers = {
        "x-apisports-key": API_FOOTBALL_KEY
    }
    
    # Dynamic Season Calculation
    # If month is >= 8 (August), we are in the start of a new season (e.g. Aug 2023 -> Season 2023)
    # If month is < 8 (e.g. Jan-July), we are in the second half of the season (e.g. May 2024 -> Season 2023)
    current_date = datetime.now()
    current_season = current_date.year if current_date.month >= 8 else current_date.year - 1

    async with httpx.AsyncClient() as client:
        for league_name, league_id in LEAGUES.items():
            try:
                url = f"{API_FOOTBALL_BASE}/fixtures"
                params = {
                    "league": league_id,
                    "season": current_season
                }
                response = await client.get(url, headers=headers, params=params)
                data = response.json()

                logger.info(f"Fetched {len(data['response'])} fixtures for {league_name}")
                logger.debug(f"Data: {data}")
                
                if "response" not in data:
                    logger.error(f"Error fetching fixtures for {league_name}: {data}")
                    continue

                for fixture in data["response"]:
                    fixture_id = fixture["fixture"]["id"]
                    match_date = datetime.fromisoformat(fixture["fixture"]["date"])
                    
                    # Check if match exists
                    stmt = select(Match).where(Match.fixture_id == fixture_id)
                    result = await session.execute(stmt)
                    existing_match = result.scalar_one_or_none()
                    
                    if not existing_match:
                        new_match = Match(
                            fixture_id=fixture_id,
                            league_id=league_id,
                            home_team=fixture["teams"]["home"]["name"],
                            away_team=fixture["teams"]["away"]["name"],
                            start_time=match_date,
                            status=fixture["fixture"]["status"]["short"]
                        )
                        session.add(new_match)
                
                await session.commit()
                
            except Exception as e:
                logger.error(f"Failed to fetch matches for {league_name}: {e}")

async def fetch_prop_lines(session: AsyncSession):
    """Fetch player prop lines from The Odds API with full parsing."""
    logger.info("Fetching prop lines")
    
    async with httpx.AsyncClient() as client:
        for league_name, sport_key in SPORT_KEYS.items():
            try:
                # 1. Get Events first
                events_url = f"{THE_ODDS_API_BASE}/{sport_key}/events"
                events_resp = await client.get(events_url, params={"apiKey": THE_ODDS_API_KEY})
                events = events_resp.json()
                
                if not isinstance(events, list):
                    continue

                for event in events:
                    event_id = event['id']
                    
                    # 2. Get Odds for specific markets
                    odds_url = f"{THE_ODDS_API_BASE}/{sport_key}/events/{event_id}/odds"
                    params = {
                        "apiKey": THE_ODDS_API_KEY,
                        "regions": "eu",
                        "markets": "h2h,player_shots,player_shots_on_target,player_assists,player_goal_scorer_anytime,player_to_receive_card",
                        "oddsFormat": "decimal"
                    }
                    odds_resp = await client.get(odds_url, params=params)
                    odds_data = odds_resp.json()
                    
                    # Create/Find Match HERE
                    event_home_team = event['home_team']
                    event_away_team = event['away_team']
                    event_commence_time = datetime.fromisoformat(event['commence_time'].replace('Z', '+00:00'))
                    
                    stmt_match = select(Match).where(
                        Match.home_team == event_home_team,
                        Match.start_time >= event_commence_time - timedelta(hours=24),
                        Match.start_time <= event_commence_time + timedelta(hours=24)
                    )
                    result_match = await session.execute(stmt_match)
                    match = result_match.scalar_one_or_none()
                    
                    if not match:
                        # Fallback: Try away team
                        stmt_match = select(Match).where(
                            Match.away_team == event['away_team'],
                            Match.start_time >= event_commence_time - timedelta(hours=24),
                            Match.start_time <= event_commence_time + timedelta(hours=24)
                        )
                        result_match = await session.execute(stmt_match)
                        match = result_match.scalar_one_or_none()

                    if not match:
                        # Create Match from The Odds API event
                        logger.info(f"Creating match from Odds API: {event_home_team} vs {event['away_team']}")
                        new_match = Match(
                            fixture_id=None, # No API Football ID
                            league_id=LEAGUES.get(league_name, 0),
                            home_team=event_home_team,
                            away_team=event['away_team'],
                            start_time=event_commence_time,
                            status='NS'
                        )
                        session.add(new_match)
                        await session.flush()
                        match = new_match
                    else:
                        logger.info(f"Found existing match: {match.home_team} vs {match.away_team}")

                    bookmakers = odds_data.get('bookmakers', [])
                    if not bookmakers:
                        logger.info(f"No bookmakers for event {event_home_team} vs {event_away_team}")
                    else:
                        logger.info(f"Found {len(bookmakers)} bookmakers for event {event_home_team} vs {event_away_team}")

                        for bookmaker in bookmakers:
                            bm_name = bookmaker['title']
                            for market in bookmaker['markets']:
                                market_key = market['key']
                                
                                # Handle Match Odds (H2H)
                                if market_key == 'h2h':
                                    for outcome in market['outcomes']:
                                        price = outcome['price']
                                        name = outcome['name']
                                        
                                        if name == event_home_team:
                                            match.odds_home = price
                                        elif name == event_away_team:
                                            match.odds_away = price
                                        elif name == 'Draw':
                                            match.odds_draw = price
                                    continue 
                                
                                # Handle Player Props
                                for outcome in market['outcomes']:
                                    player_name = outcome.get('description')
                                    if not player_name:
                                        continue

                                    line = outcome.get('point')
                                    price = outcome['price']
                                    name = outcome['name']
                                    
                                    # Normalize name
                                    name_norm = name.lower().strip()
                                    
                                    if market_key == 'player_shots':
                                        logger.debug(f"Outcome: {name} (Norm: {name_norm}) | Line: {line} | Price: {price} | Desc: {player_name}")
                                    
                                    if line is None:
                                        # Handle Yes/No markets
                                        if market_key == 'player_goal_scorer_anytime':
                                            line = 0.5
                                            if name_norm == 'yes': name_norm = 'over'
                                            if name_norm == 'no': name_norm = 'under'
                                        elif market_key == 'player_to_receive_card':
                                            line = 0.5
                                            if name_norm == 'yes': name_norm = 'over'
                                            if name_norm == 'no': name_norm = 'under'
                                        else:
                                            continue
                                        
                                    # Find or create player
                                    stmt = select(Player).where(Player.name == player_name)
                                    result = await session.execute(stmt)
                                    player = result.scalar_one_or_none()
                                    
                                    if not player:
                                        player = Player(name=player_name, team="Unknown", position="Unknown")
                                        session.add(player)
                                        await session.flush()
                                    
                                    # Store Prop Line
                                    stmt = select(PropLine).where(
                                        PropLine.player_id == player.id,
                                        PropLine.prop_type == market_key,
                                        PropLine.line == line,
                                        PropLine.bookmaker == bm_name,
                                        PropLine.match_id == match.id
                                    )
                                    result = await session.execute(stmt)
                                    existing_prop = result.scalar_one_or_none()
                                    
                                    if existing_prop:
                                        if name_norm == 'over':
                                            existing_prop.odds_over = price
                                        elif name_norm == 'under':
                                            existing_prop.odds_under = price
                                        existing_prop.timestamp = datetime.utcnow()
                                    else:
                                        new_prop = PropLine(
                                            player_id=player.id,
                                            match_id=match.id,
                                            prop_type=market_key,
                                            line=line,
                                            bookmaker=bm_name,
                                            odds_over=price if name_norm == 'over' else 0,
                                            odds_under=price if name_norm == 'under' else 0,
                                            timestamp=datetime.utcnow()
                                        )
                                        session.add(new_prop)
                                        await session.flush()
                    
                    await session.commit()

            except Exception as e:
                logger.error(f"Failed to fetch odds for {league_name}: {e}")

async def fetch_player_stats(session: AsyncSession):
    """Fetch player stats for recently finished matches."""
    logger.info("Fetching player stats for finished matches")
    
    # Find matches finished in the last 7 days that might need stats
    # Ideally we'd check if we already have stats for them, but for now just look back a bit
    # A better check: Match.status == 'FT' AND NOT EXISTS(HistoricalStat where match_date = match.start_time)
    # But date matching is fuzzy. Let's just grab recent FT matches.
    
    stmt = select(Match).where(
        Match.status == 'FT',
        Match.start_time >= datetime.now() - timedelta(days=3)
    )
    result = await session.execute(stmt)
    matches = result.scalars().all()
    
    if not matches:
        logger.info("No recent finished matches found to fetch stats for.")
        return

    headers = {
        "x-apisports-key": API_FOOTBALL_KEY
    }
    
    async with httpx.AsyncClient() as client:
        for match in matches:
            if not match.fixture_id:
                continue
                
            # Check if we already have stats for this match
            # We check if any HistoricalStat exists for this date and these teams
            stmt_check = select(HistoricalStat).where(
                HistoricalStat.match_date == match.start_time.date(),
                HistoricalStat.opponent.in_([match.home_team, match.away_team])
            ).limit(1)
            result_check = await session.execute(stmt_check)
            if result_check.scalar_one_or_none():
                logger.info(f"Stats already exist for {match.home_team} vs {match.away_team}, skipping.")
                continue
            
            try:
                logger.info(f"Fetching stats for match {match.home_team} vs {match.away_team} (ID: {match.fixture_id})")
                url = f"{API_FOOTBALL_BASE}/fixtures/players"
                params = {"fixture": match.fixture_id}
                
                response = await client.get(url, headers=headers, params=params)
                data = response.json()
                
                if "response" not in data:
                    logger.error(f"Error fetching stats for match {match.fixture_id}: {data}")
                    continue
                    
                for team_data in data["response"]:
                    team_name = team_data["team"]["name"]
                    
                    for player_data in team_data["players"]:
                        p_info = player_data["player"]
                        stats = player_data["statistics"][0] # Usually only 1 item for the match
                        
                        # Find or Create Player
                        stmt_p = select(Player).where(Player.player_id == p_info["id"])
                        result_p = await session.execute(stmt_p)
                        player = result_p.scalar_one_or_none()
                        
                        if not player:
                            player = Player(
                                player_id=p_info["id"],
                                name=p_info["name"],
                                team=team_name,
                                position=stats["games"]["position"] or "Unknown"
                            )
                            session.add(player)
                            await session.flush()
                        
                        # Create HistoricalStat
                        # Check for duplicate (same player, same date)
                        stmt_hs = select(HistoricalStat).where(
                            HistoricalStat.player_id == player.id,
                            HistoricalStat.match_date == match.start_time.date()
                        )
                        result_hs = await session.execute(stmt_hs)
                        existing_stat = result_hs.scalar_one_or_none()
                        
                        if not existing_stat:
                            new_stat = HistoricalStat(
                                player_id=player.id,
                                match_date=match.start_time.date(),
                                opponent=match.away_team if team_name == match.home_team else match.home_team,
                                minutes_played=stats["games"]["minutes"] or 0,
                                shots=stats["shots"]["total"] or 0,
                                shots_on_target=stats["shots"]["on"] or 0,
                                assists=stats["goals"]["assists"] or 0,
                                passes=stats["passes"]["total"] or 0,
                                tackles=stats["tackles"]["total"] or 0,
                                cards=(stats["cards"]["yellow"] or 0) + (stats["cards"]["red"] or 0)
                            )
                            session.add(new_stat)
                
                await session.commit()
                
            except Exception as e:
                logger.error(f"Failed to fetch stats for match {match.fixture_id}: {e}")

async def run_ingestion():
    async with SessionLocal() as session:
        await fetch_upcoming_matches(session)
        await fetch_prop_lines(session)
        await fetch_player_stats(session)

if __name__ == "__main__":
    asyncio.run(run_ingestion())
