import httpx
import os
import asyncio
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ..core.models import Match, Player, PropLine, HistoricalStat
from ..core.database import SessionLocal
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

async def fetch_match_odds(session: AsyncSession):
    """Fetch Over/Under 2.5 and BTTS odds from The Odds API."""
    logger.info("Fetching match odds (Over/Under 2.5 and BTTS)")
    
    async with httpx.AsyncClient() as client:
        for league_name, sport_key in SPORT_KEYS.items():
            try:
                # Get events
                events_url = f"{THE_ODDS_API_BASE}/{sport_key}/events"
                events_resp = await client.get(events_url, params={"apiKey": THE_ODDS_API_KEY})
                events = events_resp.json()
                
                if not isinstance(events, list):
                    continue
                
                for event in events:
                    event_id = event.get("id")
                    if not event_id:
                        continue
                    
                    # Get odds for this event
                    odds_url = f"{THE_ODDS_API_BASE}/{sport_key}/events/{event_id}/odds"
                    odds_resp = await client.get(odds_url, params={"apiKey": THE_ODDS_API_KEY})
                    odds_data = odds_resp.json()
                    
                    if not isinstance(odds_data, dict) or "bookmakers" not in odds_data:
                        continue
                    
                    # Find match in database by teams
                    home_team = event.get("home_team")
                    away_team = event.get("away_team")
                    
                    if not home_team or not away_team:
                        continue
                    
                    stmt = select(Match).where(
                        Match.home_team == home_team,
                        Match.away_team == away_team,
                        Match.status == 'NS'  # Only upcoming matches
                    )
                    result = await session.execute(stmt)
                    match = result.scalar_one_or_none()
                    
                    if not match:
                        continue
                    
                    # Parse odds from bookmakers
                    odds_over_2_5 = None
                    odds_under_2_5 = None
                    odds_btts_yes = None
                    odds_btts_no = None
                    
                    for bookmaker in odds_data.get("bookmakers", []):
                        for market in bookmaker.get("markets", []):
                            market_key = market.get("key")
                            
                            if market_key == "totals":
                                # Over/Under 2.5 goals
                                for outcome in market.get("outcomes", []):
                                    name = outcome.get("name", "").lower()
                                    price = outcome.get("price")
                                    
                                    if "over" in name and "2.5" in name:
                                        if odds_over_2_5 is None or price < odds_over_2_5:
                                            odds_over_2_5 = price
                                    elif "under" in name and "2.5" in name:
                                        if odds_under_2_5 is None or price < odds_under_2_5:
                                            odds_under_2_5 = price
                            
                            elif market_key == "btts":
                                # Both Teams To Score
                                for outcome in market.get("outcomes", []):
                                    name = outcome.get("name", "").lower()
                                    price = outcome.get("price")
                                    
                                    if "yes" in name:
                                        if odds_btts_yes is None or price < odds_btts_yes:
                                            odds_btts_yes = price
                                    elif "no" in name:
                                        if odds_btts_no is None or price < odds_btts_no:
                                            odds_btts_no = price
                    
                    # Update match with odds
                    if odds_over_2_5:
                        match.odds_over_2_5 = odds_over_2_5
                    if odds_under_2_5:
                        match.odds_under_2_5 = odds_under_2_5
                    if odds_btts_yes:
                        match.odds_btts_yes = odds_btts_yes
                    if odds_btts_no:
                        match.odds_btts_no = odds_btts_no
                    
                    await session.commit()
                    
            except Exception as e:
                logger.error(f"Failed to fetch match odds for {league_name}: {e}")

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

async def fetch_api_football_odds(session: AsyncSession):
    """
    Fetch pre-match odds from API-Football for upcoming matches.
    We fetch by date (today and tomorrow) to optimize API calls.
    """
    logger.info("Fetching pre-match odds from API-Football")
    
    headers = {
        "x-apisports-key": API_FOOTBALL_KEY
    }
    
    # Dates to fetch: Today and Tomorrow
    dates_to_fetch = [
        datetime.now().date(),
        (datetime.now() + timedelta(days=1)).date()
    ]
    
    # Determine season
    current_date = datetime.now()
    current_season = current_date.year if current_date.month >= 8 else current_date.year - 1

    async with httpx.AsyncClient() as client:
        for date in dates_to_fetch:
            date_str = date.strftime("%Y-%m-%d")
            
            for league_name, league_id in LEAGUES.items():
                try:
                    url = f"{API_FOOTBALL_BASE}/odds"
                    params = {
                        "league": league_id,
                        "season": current_season,
                        "date": date_str,
                        "bookmaker": 8  # Bet365
                    }
                    
                    logger.info(f"Fetching odds for {league_name} on {date_str}")
                    response = await client.get(url, headers=headers, params=params)
                    data = response.json()
                    
                    if "response" not in data:
                        logger.error(f"Error fetching odds for {league_name} on {date_str}: {data}")
                        continue
                        
                    logger.info(f"Found odds for {len(data['response'])} fixtures")
                    
                    for item in data["response"]:
                        fixture_id = item["fixture"]["id"]
                        bookmakers = item["bookmakers"]
                        
                        if not bookmakers:
                            continue
                            
                        # We requested Bet365 (id 8), so it should be the first one
                        bookmaker = bookmakers[0]
                        
                        # Find match in DB
                        stmt = select(Match).where(Match.fixture_id == fixture_id)
                        result = await session.execute(stmt)
                        match = result.scalar_one_or_none()
                        
                        if not match:
                            continue
                            
                        # Parse bets
                        for bet in bookmaker["bets"]:
                            bet_id = bet["id"]
                            values = bet["values"]
                            
                            # 1: Match Winner (1x2)
                            if bet_id == 1:
                                for val in values:
                                    if val["value"] == "Home":
                                        match.odds_home = float(val["odd"])
                                    elif val["value"] == "Draw":
                                        match.odds_draw = float(val["odd"])
                                    elif val["value"] == "Away":
                                        match.odds_away = float(val["odd"])
                                        
                            # 5: Goals Over/Under
                            elif bet_id == 5:
                                for val in values:
                                    if val["value"] == "Over 2.5":
                                        match.odds_over_2_5 = float(val["odd"])
                                    elif val["value"] == "Under 2.5":
                                        match.odds_under_2_5 = float(val["odd"])
                                        
                            # 8: Both Teams To Score
                            elif bet_id == 8:
                                for val in values:
                                    if val["value"] == "Yes":
                                        match.odds_btts_yes = float(val["odd"])
                                    elif val["value"] == "No":
                                        match.odds_btts_no = float(val["odd"])
                                        
                        session.add(match)
                        
                    await session.commit()
                    
                except Exception as e:
                    logger.error(f"Failed to fetch odds for {league_name} on {date_str}: {e}")

async def update_finished_matches(session: AsyncSession):
    """
    Fetch recent finished matches to update scores (FT and HT).
    We look back 3 days to ensure we catch recently finished games.
    """
    logger.info("Updating finished matches (Scores)")
    
    headers = {
        "x-apisports-key": API_FOOTBALL_KEY
    }
    
    # Look back 3 days
    start_date = (datetime.now() - timedelta(days=3)).date()
    end_date = datetime.now().date()
    
    # Determine season
    current_date = datetime.now()
    current_season = current_date.year if current_date.month >= 8 else current_date.year - 1

    async with httpx.AsyncClient() as client:
        for league_name, league_id in LEAGUES.items():
            try:
                url = f"{API_FOOTBALL_BASE}/fixtures"
                params = {
                    "league": league_id,
                    "season": current_season,
                    "from": start_date.strftime("%Y-%m-%d"),
                    "to": end_date.strftime("%Y-%m-%d"),
                    "status": "FT"
                }
                
                response = await client.get(url, headers=headers, params=params)
                data = response.json()
                
                if "response" not in data:
                    logger.error(f"Error fetching finished matches for {league_name}: {data}")
                    continue
                    
                logger.info(f"Found {len(data['response'])} finished matches for {league_name}")
                
                for fixture in data["response"]:
                    fixture_id = fixture["fixture"]["id"]
                    
                    # Find match in DB
                    stmt = select(Match).where(Match.fixture_id == fixture_id)
                    result = await session.execute(stmt)
                    match = result.scalar_one_or_none()
                    
                    if not match:
                        continue
                        
                    # Update scores
                    score = fixture["score"]
                    goals = fixture["goals"]
                    
                    match.status = "FT"
                    match.home_score = goals["home"]
                    match.away_score = goals["away"]
                    match.home_half_time_goals = score["halftime"]["home"]
                    match.away_half_time_goals = score["halftime"]["away"]
                    
                    session.add(match)
                    
                await session.commit()
                
            except Exception as e:
                logger.error(f"Failed to update finished matches for {league_name}: {e}")

async def fetch_match_statistics(session: AsyncSession):
    """
    Fetch detailed match statistics (shots, corners, etc.) for finished matches.
    """
    logger.info("Fetching match statistics")
    
    headers = {
        "x-apisports-key": API_FOOTBALL_KEY
    }
    
    # Find matches that are FT but missing statistics (e.g., home_shots is None)
    # We limit to recent matches to avoid hammering the API for old data
    stmt = select(Match).where(
        Match.status == 'FT',
        Match.home_shots.is_(None),
        Match.start_time >= datetime.now() - timedelta(days=7)
    )
    result = await session.execute(stmt)
    matches = result.scalars().all()
    
    if not matches:
        logger.info("No matches found needing statistics update")
        return
        
    logger.info(f"Found {len(matches)} matches needing statistics")
    
    async with httpx.AsyncClient() as client:
        for match in matches:
            try:
                url = f"{API_FOOTBALL_BASE}/fixtures/statistics"
                params = {
                    "fixture": match.fixture_id
                }
                
                response = await client.get(url, headers=headers, params=params)
                data = response.json()
                
                if "response" not in data:
                    logger.error(f"Error fetching stats for fixture {match.fixture_id}: {data}")
                    continue
                
                if not data["response"]:
                    logger.info(f"No statistics available for fixture {match.fixture_id}")
                    continue
                    
                # Response is a list of 2 items (one for each team)
                for team_stat in data["response"]:
                    team_id = team_stat["team"]["id"]
                    is_home = (team_stat["team"]["name"] == match.home_team)
                    
                    stats = {item["type"]: item["value"] for item in team_stat["statistics"]}
                    
                    # Helper to safely get int value
                    def get_val(key):
                        val = stats.get(key)
                        return int(val) if val is not None else 0
                    
                    if is_home:
                        match.home_shots = get_val("Total Shots")
                        match.home_shots_on_target = get_val("Shots on Goal")
                        match.home_corners = get_val("Corner Kicks")
                        match.home_fouls = get_val("Fouls")
                        match.home_yellow_cards = get_val("Yellow Cards")
                        match.home_red_cards = get_val("Red Cards")
                    else:
                        match.away_shots = get_val("Total Shots")
                        match.away_shots_on_target = get_val("Shots on Goal")
                        match.away_corners = get_val("Corner Kicks")
                        match.away_fouls = get_val("Fouls")
                        match.away_yellow_cards = get_val("Yellow Cards")
                        match.away_red_cards = get_val("Red Cards")
                        
                session.add(match)
                await session.commit()
                
            except Exception as e:
                logger.error(f"Failed to fetch stats for fixture {match.fixture_id}: {e}")

async def run_ingestion():
    async with SessionLocal() as session:
        await fetch_upcoming_matches(session)
        await update_finished_matches(session) # Update scores for recent games
        await fetch_prop_lines(session)
        await fetch_match_odds(session) # Keep The Odds API for backup/comparison if needed
        await fetch_api_football_odds(session) # New API-Football odds
        await fetch_match_statistics(session) # Match-level stats (shots, etc.)
        await fetch_player_stats(session) # Player-level stats

if __name__ == "__main__":
    asyncio.run(run_ingestion())
