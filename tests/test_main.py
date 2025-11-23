import pytest
from httpx import AsyncClient
from app.main import app
from app.auth import get_api_key

# Mock auth
async def mock_get_api_key():
    return "test_key"

app.dependency_overrides[get_api_key] = mock_get_api_key

@pytest.mark.asyncio
async def test_health_check():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

@pytest.mark.asyncio
async def test_get_leagues():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/leagues")
    assert response.status_code == 200
    assert len(response.json()) > 0
