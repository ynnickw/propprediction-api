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
    "Premier League": 39,
    "Bundesliga": 78,
    "Champions League": 2,
    "La Liga": 140,
    "Serie A": 135
}

# The Odds API Sport Keys
SPORT_KEYS = {
    "Premier League": "soccer_epl",
    "Bundesliga": "soccer_germany_bundesliga",
    "Champions League": "soccer_uefa_champs_league",
    "La Liga": "soccer_spain_la_liga",
    "Serie A": "soccer_italy_serie_a"
}

async def fetch_upcoming_matches(session: AsyncSession):
    """Fetch matches for the next 48 hours."""
    logger.info("Fetching upcoming matches")
    headers = {
        "x-rapidapi-host": "v3.football.api-sports.io",
        "x-rapidapi-key": API_FOOTBALL_KEY
    }
    
    async with httpx.AsyncClient() as client:
        for league_name, league_id in LEAGUES.items():
            try:
                url = f"{API_FOOTBALL_BASE}/fixtures"
                params = {
                    "league": league_id,
                    "season": 2020, # TODO: Dynamic season
                    "from": datetime.now().strftime("%Y-%m-%d"),
                    "to": (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")
                }
                response = await client.get(url, headers=headers, params=params)
                data = response.json()
                
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
                        "regions": "eu,uk",
                        "markets": "player_shots,player_shots_on_goal,player_assists",
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
                    for bookmaker in bookmakers:
                        bm_name = bookmaker['title']
                        for market in bookmaker['markets']:
                            market_key = market['key'] # e.g. player_shots
                            
                            for outcome in market['outcomes']:
                                player_name = outcome['description']
                                line = outcome.get('point') # The handicap/line
                                price = outcome['price']
                                name = outcome['name'] # Over or Under
                                
                                if line is None:
                                    continue
                                    
                                # Find or create player
                                # Note: Name matching is tricky. Ideally use fuzzy match or ID map.
                                # For now, exact match or create new.
                                stmt = select(Player).where(Player.name == player_name)
                                result = await session.execute(stmt)
                                player = result.scalar_one_or_none()
                                
                                if not player:
                                    player = Player(name=player_name, team="Unknown", position="Unknown")
                                    session.add(player)
                                    await session.flush() # Get ID
                                
                                # Store Prop Line
                                # Check if exists to update
                                stmt = select(PropLine).where(
                                    PropLine.player_id == player.id,
                                    PropLine.prop_type == market_key,
                                    PropLine.line == line,
                                    PropLine.bookmaker == bm_name
                                )
                    if not bookmakers:
                        logger.info(f"No bookmakers for event {event_home_team} vs {event_away_team}")
                    else:
                        logger.info(f"Found {len(bookmakers)} bookmakers for event {event_home_team} vs {event_away_team}")

                        for bookmaker in bookmakers:
                            bm_name = bookmaker['title']
                            for market in bookmaker['markets']:
                                market_key = market['key'] # e.g. player_shots
                                
                                for outcome in market['outcomes']:
                                    player_name = outcome['description']
                                    line = outcome.get('point') # The handicap/line
                                    price = outcome['price']
                                    name = outcome['name'] # Over or Under
                                    
                                    if line is None:
                                        continue
                                        
                                    # Find or create player
                                    # Note: Name matching is tricky. Ideally use fuzzy match or ID map.
                                    # For now, exact match or create new.
                                    stmt = select(Player).where(Player.name == player_name)
                                    result = await session.execute(stmt)
                                    player = result.scalar_one_or_none()
                                    
                                    if not player:
                                        player = Player(name=player_name, team="Unknown", position="Unknown")
                                        session.add(player)
                                        await session.flush() # Get ID
                                    
                                    # Store Prop Line
                                    # Check if exists to update
                                    stmt = select(PropLine).where(
                                        PropLine.player_id == player.id,
                                        PropLine.prop_type == market_key,
                                        PropLine.line == line,
                                        PropLine.bookmaker == bm_name,
                                        PropLine.match_id == match.id # Link to the found/created match
                                    )
                                    result = await session.execute(stmt)
                                    existing_prop = result.scalar_one_or_none()
                                    
                                    if existing_prop:
                                        if name == 'Over':
                                            existing_prop.odds_over = price
                                        else:
                                            existing_prop.odds_under = price
                                        existing_prop.timestamp = datetime.utcnow()
                                        logger.debug(f"Updated existing prop line for {player_name} ({market_key} {line}) from {bm_name}")
                                    else:
                                        new_prop = PropLine(
                                            player_id=player.id,
                                            match_id=match.id, # Link to the found/created match
                                            prop_type=market_key,
                                            line=line,
                                            bookmaker=bm_name,
                                            odds_over=price if name == 'Over' else 0,
                                            odds_under=price if name == 'Under' else 0,
                                            timestamp=datetime.utcnow()
                                        )
                                        session.add(new_prop)
                                        logger.debug(f"Added new prop line for {player_name} ({market_key} {line}) from {bm_name}")
                    
                    await session.commit()

            except Exception as e:
                logger.error(f"Failed to fetch odds for {league_name}: {e}")

async def fetch_player_stats(session: AsyncSession):
    """Fetch detailed historical player stats from API Football."""
    # This would involve iterating over all players in DB, 
    # calling /players/fixtures endpoint, and storing detailed stats.
    # Due to API rate limits, this should be done carefully in batches.
    pass

async def run_ingestion():
    async with SessionLocal() as session:
        await fetch_upcoming_matches(session)
        await fetch_prop_lines(session)
        # await fetch_player_stats(session)

if __name__ == "__main__":
    asyncio.run(run_ingestion())
