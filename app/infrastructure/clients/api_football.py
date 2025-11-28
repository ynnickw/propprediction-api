import httpx
from typing import Dict, Any, List
from app.config import settings
import structlog

logger = structlog.get_logger()

class ApiFootballClient:
    def __init__(self):
        self.base_url = settings.API_FOOTBALL_BASE
        self.headers = {
            "x-apisports-key": settings.API_FOOTBALL_KEY
        }

    async def get_fixtures(self, league_id: int, season: int) -> List[Dict[str, Any]]:
        """Fetch fixtures for a specific league and season."""
        async with httpx.AsyncClient() as client:
            try:
                url = f"{self.base_url}/fixtures"
                params = {
                    "league": league_id,
                    "season": season
                }
                response = await client.get(url, headers=self.headers, params=params)
                data = response.json()
                
                if "response" not in data:
                    logger.error(f"Error fetching fixtures: {data}")
                    return []
                
                return data["response"]
            except Exception as e:
                logger.error(f"Failed to fetch fixtures: {e}")
                return []
