# App Folder Structure

This document describes the organization of the `app/` folder.

## Directory Structure

```
app/
├── __init__.py              # Main app package initialization
├── api/                     # API Layer
│   ├── __init__.py
│   ├── main.py             # FastAPI application and routes
│   └── auth.py             # API authentication
│
├── core/                    # Core Infrastructure
│   ├── __init__.py
│   ├── database.py         # Database connection and session management
│   ├── models.py           # SQLAlchemy database models
│   ├── schemas.py          # Pydantic response schemas
│   └── utils.py            # Utility functions (logging, etc.)
│
├── ml/                      # Machine Learning
│   ├── __init__.py
│   ├── model.py            # EnsembleModel class and prediction logic
│   ├── train.py            # Player prop model training
│   ├── train_match.py      # Match-level model training
│   ├── features.py         # Player feature engineering
│   ├── match_features.py   # Match feature engineering
│   └── match_predictions.py # Match prediction logic and edge calculation
│
├── data/                    # Data Ingestion
│   ├── __init__.py
│   ├── data_ingestion.py   # API data fetching (matches, props, odds)
│   ├── collect_player_data.py  # Player data collection
│   └── prepare_full_dataset.py # Dataset preparation
│
├── services/                # Business Logic Services
│   ├── __init__.py
│   └── scheduler.py        # Pipeline orchestration and scheduling
│
└── scripts/                 # Utility Scripts
    ├── __init__.py
    └── init_db.py          # Database initialization
```

## Import Patterns

### From API Layer
```python
from ..core.database import get_db
from ..core.models import DailyPick, Match
from ..core.schemas import PickResponse
from ..services.scheduler import start_scheduler
```

### From ML Module
```python
from ..core.models import Player, Match, HistoricalStat
from .model import EnsembleModel
from .match_features import engineer_over_under_2_5_features
```

### From Services
```python
from ..data.data_ingestion import run_ingestion
from ..core.models import Match, DailyPick
from ..ml.features import prepare_features
from ..ml.model import predict_props
```

### From Data Module
```python
from ..core.models import Match, Player
from ..core.database import SessionLocal
```

## Module Responsibilities

### `api/`
- FastAPI route definitions
- Request/response handling
- Authentication middleware

### `core/`
- Database configuration and models
- Shared utilities
- Response schemas

### `ml/`
- Model training scripts
- Feature engineering
- Prediction logic
- Model inference

### `data/`
- External API integration
- Data collection and preparation
- Dataset processing

### `services/`
- Scheduled tasks
- Pipeline orchestration
- Business logic coordination

### `scripts/`
- One-time setup scripts
- Database initialization
- Utility scripts

## Migration Notes

All imports have been updated to use the new structure. The main entry point remains:
```python
from app import app  # or from app.api.main import app
```

