import httpx
from typing import Dict, Any, List, Optional
from app.config import settings
import structlog

logger = structlog.get_logger()

class OddsApiClient:
    def __init__(self):
        self.base_url = settings.THE_ODDS_API_BASE
        self.api_key = settings.THE_ODDS_API_KEY

    async def get_events(self, sport_key: str) -> List[Dict[str, Any]]:
        """Fetch upcoming events for a sport."""
        async with httpx.AsyncClient() as client:
            try:
                url = f"{self.base_url}/{sport_key}/events"
                params = {"apiKey": self.api_key}
                response = await client.get(url, params=params)
                data = response.json()
                
                if not isinstance(data, list):
                    logger.error(f"Error fetching events for {sport_key}: {data}")
                    return []
                
                return data
            except Exception as e:
                logger.error(f"Failed to fetch events for {sport_key}: {e}")
                return []

    async def get_odds(self, sport_key: str, event_id: str, markets: str) -> Dict[str, Any]:
        """Fetch odds for a specific event and markets."""
        async with httpx.AsyncClient() as client:
            try:
                url = f"{self.base_url}/{sport_key}/events/{event_id}/odds"
                params = {
                    "apiKey": self.api_key,
                    "regions": "eu",
                    "markets": markets,
                    "oddsFormat": "decimal"
                }
                response = await client.get(url, params=params)
                data = response.json()
                
                if not isinstance(data, dict):
                    logger.error(f"Error fetching odds for event {event_id}: {data}")
                    return {}
                
                return data
            except Exception as e:
                logger.error(f"Failed to fetch odds for event {event_id}: {e}")
                return {}
