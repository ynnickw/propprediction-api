import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    API_FOOTBALL_KEY: str = os.getenv("API_FOOTBALL_KEY", "")
    THE_ODDS_API_KEY: str = os.getenv("THE_ODDS_API_KEY", "")
    
    # API Base URLs
    API_FOOTBALL_BASE: str = "https://v3.football.api-sports.io"
    THE_ODDS_API_BASE: str = "https://api.the-odds-api.com/v4/sports"
    MODEL_DIR: str = "models"
    
    # Optional/Legacy
    REDIS_URL: str = "redis://localhost:6379/0"
    SECRET_KEY: str = "default_secret_key"
    ENVIRONMENT: str = "development"

    class Config:
        env_file = ".env"
        extra = "ignore"
        case_sensitive = True

settings = Settings()
