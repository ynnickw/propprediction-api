import structlog
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.infrastructure.clients.api_football import ApiFootballClient
from app.infrastructure.clients.odds_api import OddsApiClient
from app.domain.models import Match, Player, PropLine
from app.config.constants import LEAGUES, SPORT_KEYS

logger = structlog.get_logger()

class DataService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.api_football = ApiFootballClient()
        self.odds_api = OddsApiClient()

    async def _get_or_create_team(self, team_name: str, league_id: int = None) -> int:
        """Get team ID by name, or create if not exists."""
        from app.domain.models import Team
        
        # Map league_id to league name
        league_name_map = {
            78: "Bundesliga",
            39: "Premier League",
            140: "La Liga"
        }
        league_name = league_name_map.get(league_id, str(league_id)) if league_id else None
        
        # Try to find team
        stmt = select(Team).where(Team.name == team_name)
        result = await self.session.execute(stmt)
        team = result.scalar_one_or_none()
        
        if team:
            return team.id
            
        # Create new team
        new_team = Team(name=team_name, league=league_name)
        self.session.add(new_team)
        await self.session.flush() # Get ID
        return new_team.id

    async def fetch_upcoming_matches(self):
        """Fetch matches for the next 48 hours."""
        logger.info("Fetching upcoming matches")
        from app.config.constants import API_FOOTBALL_TO_DB_MAPPING
        
        # Dynamic Season Calculation
        current_date = datetime.now()
        current_season = current_date.year if current_date.month >= 8 else current_date.year - 1

        for league_name, league_id in LEAGUES.items():
            fixtures = await self.api_football.get_fixtures(league_id, current_season)
            logger.info(f"Fetched {len(fixtures)} fixtures for {league_name}")
            
            for fixture in fixtures:
                fixture_id = fixture["fixture"]["id"]
                match_date = datetime.fromisoformat(fixture["fixture"]["date"])
                
                # Check if match exists
                stmt = select(Match).where(Match.fixture_id == fixture_id)
                result = await self.session.execute(stmt)
                existing_match = result.scalar_one_or_none()
                
                if not existing_match:
                    # Resolve Team IDs with name normalization
                    home_team_name_raw = fixture["teams"]["home"]["name"]
                    away_team_name_raw = fixture["teams"]["away"]["name"]
                    
                    # Normalize team names using mapping
                    home_team_name = API_FOOTBALL_TO_DB_MAPPING.get(home_team_name_raw, home_team_name_raw)
                    away_team_name = API_FOOTBALL_TO_DB_MAPPING.get(away_team_name_raw, away_team_name_raw)
                    
                    logger.debug(f"API-Football Match: {home_team_name_raw} vs {away_team_name_raw} -> {home_team_name} vs {away_team_name}")
                    
                    home_team_id = await self._get_or_create_team(home_team_name, league_id)
                    away_team_id = await self._get_or_create_team(away_team_name, league_id)
                    
                    new_match = Match(
                        fixture_id=fixture_id,
                        league_id=league_id,
                        home_team_id=home_team_id,
                        away_team_id=away_team_id,
                        start_time=match_date,
                        status=fixture["fixture"]["status"]["short"]
                    )
                    self.session.add(new_match)
            
            await self.session.commit()

    async def fetch_match_odds(self):
        """Fetch Over/Under 2.5 and BTTS odds from The Odds API."""
        logger.info("Fetching match odds (Over/Under 2.5 and BTTS)")
        from app.domain.models import Team
        from sqlalchemy.orm import aliased
        from app.config.constants import ODDS_API_TO_DB_MAPPING
        
        HomeTeam = aliased(Team)
        AwayTeam = aliased(Team)
        
        for league_name, sport_key in SPORT_KEYS.items():
            events = await self.odds_api.get_events(sport_key)
            logger.info(f"Fetched {len(events)} events for {league_name} ({sport_key})")
            
            for event in events:
                event_id = event.get("id")
                if not event_id:
                    continue
                
                # Find match in database by teams
                home_team_name_raw = event.get("home_team")
                away_team_name_raw = event.get("away_team")
                
                if not home_team_name_raw or not away_team_name_raw:
                    continue
                
                # Normalize names using mapping
                home_team_name = ODDS_API_TO_DB_MAPPING.get(home_team_name_raw, home_team_name_raw)
                away_team_name = ODDS_API_TO_DB_MAPPING.get(away_team_name_raw, away_team_name_raw)
                
                logger.debug(f"Odds API Event: {home_team_name_raw} vs {away_team_name_raw} -> {home_team_name} vs {away_team_name}")

                # Query matches joining with Team table
                stmt = (
                    select(Match)
                    .join(HomeTeam, Match.home_team_id == HomeTeam.id)
                    .join(AwayTeam, Match.away_team_id == AwayTeam.id)
                    .where(
                        HomeTeam.name == home_team_name,
                        AwayTeam.name == away_team_name,
                        Match.status.in_(['NS', '1H', 'HT', '2H', 'ET', 'P', 'LIVE'])
                    )
                )
                result = await self.session.execute(stmt)
                matches = result.scalars().all()
                
                if not matches:
                    logger.warning(f"No match found for {home_team_name} vs {away_team_name}")
                    continue
                
                logger.info(f"Found {len(matches)} matches for {home_team_name} vs {away_team_name}")
                
                # Get odds for this event
                odds_data = await self.odds_api.get_odds(sport_key, event_id, "totals,btts")
                if not odds_data:
                    continue

                for match in matches:
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
                                    point = outcome.get("point")
                                    
                                    if "over" in name and point == 2.5:
                                        if odds_over_2_5 is None or price < odds_over_2_5:
                                            odds_over_2_5 = price
                                    elif "under" in name and point == 2.5:
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
                        logger.info(f"Updated Over 2.5 odds for {home_team_name} vs {away_team_name}: {odds_over_2_5}")
                    else:
                        logger.warning(f"No Over 2.5 odds found for {home_team_name} vs {away_team_name}")

                    if odds_under_2_5:
                        match.odds_under_2_5 = odds_under_2_5
                    if odds_btts_yes:
                        match.odds_btts_yes = odds_btts_yes
                        logger.info(f"Updated BTTS Yes odds for {home_team_name} vs {away_team_name}: {odds_btts_yes}")
                    if odds_btts_no:
                        match.odds_btts_no = odds_btts_no
                    
                    await self.session.commit()
