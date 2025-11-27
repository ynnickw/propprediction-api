# App Module Structure

This directory contains the main application code, organized into logical submodules.

## Directory Structure

```
app/
├── api/          # API endpoints and authentication
├── core/         # Database, models, schemas, utilities  
├── ml/           # Machine learning models and training
├── data/         # Data ingestion and collection
├── services/     # Business logic and scheduling
└── scripts/      # Utility scripts
```

## Module Overview

### `api/` - API Layer
- **main.py**: FastAPI application with all routes
- **auth.py**: API key authentication middleware

**Key Endpoints:**
- `GET /picks` - Get today's picks (supports `prediction_type` filter)
- `GET /picks/match` - Get match-level picks only
- `GET /picks/{date}` - Get historical picks
- `GET /leagues` - List supported leagues
- `GET /health` - Health check

### `core/` - Core Infrastructure
- **database.py**: Database connection and session management
- **models.py**: SQLAlchemy ORM models (Match, Player, DailyPick, etc.)
- **schemas.py**: Pydantic response schemas
- **utils.py**: Logging configuration and utilities

### `ml/` - Machine Learning
- **model.py**: EnsembleModel class for predictions
- **train.py**: Player prop model training
- **train_match.py**: Match-level model training (Over/Under 2.5, BTTS)
- **features.py**: Player feature engineering
- **match_features.py**: Match feature engineering
- **match_predictions.py**: Match prediction logic and edge calculation

### `data/` - Data Ingestion
- **data_ingestion.py**: Fetches matches, props, and odds from external APIs
- **collect_player_data.py**: Player statistics collection
- **prepare_full_dataset.py**: Dataset preparation and enrichment

### `services/` - Business Logic
- **scheduler.py**: Daily pipeline orchestration
  - Data ingestion
  - Player prop predictions
  - Match-level predictions (Over/Under 2.5, BTTS)
  - Pick storage

### `scripts/` - Utility Scripts
- **init_db.py**: Database initialization

## Import Examples

```python
# API
from app.api.main import app
from app.api.auth import get_api_key

# Core
from app.core.models import Match, DailyPick
from app.core.database import get_db, SessionLocal
from app.core.schemas import PickResponse

# ML
from app.ml.train_match import train_over_under_2_5
from app.ml.match_features import engineer_over_under_2_5_features
from app.ml.model import EnsembleModel

# Data
from app.data.data_ingestion import run_ingestion

# Services
from app.services.scheduler import start_scheduler
```

## Running Commands

### Training Models
```bash
# Player prop models
python -m app.ml.train

# Match models
python -m app.ml.train_match --prop-type over_under_2.5
python -m app.ml.train_match --prop-type btts
```

### Running Pipeline
```bash
python -c "from app.services.scheduler import pipeline_job; import asyncio; asyncio.run(pipeline_job())"
```

### Starting API
```bash
uvicorn app.api.main:app --reload
```

## Notes

- All imports use relative paths within the app package
- The main app can be imported as `from app import app` (lazy loading)
- Direct module imports (e.g., `from app.ml.match_features import ...`) work without loading FastAPI dependencies

