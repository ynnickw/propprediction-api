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

    async def fetch_upcoming_matches(self):
        """Fetch matches for the next 48 hours."""
        logger.info("Fetching upcoming matches")
        
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
                    new_match = Match(
                        fixture_id=fixture_id,
                        league_id=league_id,
                        home_team=fixture["teams"]["home"]["name"],
                        away_team=fixture["teams"]["away"]["name"],
                        start_time=match_date,
                        status=fixture["fixture"]["status"]["short"]
                    )
                    self.session.add(new_match)
            
            await self.session.commit()

    async def fetch_match_odds(self):
        """Fetch Over/Under 2.5 and BTTS odds from The Odds API."""
        logger.info("Fetching match odds (Over/Under 2.5 and BTTS)")
        
        for league_name, sport_key in SPORT_KEYS.items():
            events = await self.odds_api.get_events(sport_key)
            
            for event in events:
                event_id = event.get("id")
                if not event_id:
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
                result = await self.session.execute(stmt)
                matches = result.scalars().all()
                
                if not matches:
                    continue
                
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
                    
                    await self.session.commit()
