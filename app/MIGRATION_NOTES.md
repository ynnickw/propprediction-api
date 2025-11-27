# Migration Notes: App Folder Restructure

## Changes Made

The `app/` folder has been restructured into logical subfolders for better organization and maintainability.

## New Structure

```
app/
├── api/          # API endpoints and authentication
├── core/         # Database, models, schemas, utilities
├── ml/           # Machine learning models and training
├── data/         # Data ingestion and collection
├── services/     # Business logic and scheduling
└── scripts/      # Utility scripts
```

## Import Changes

### Old Imports (No Longer Work)
```python
from app.main import app
from app.models import Match
from app.database import get_db
from app.train_match import train_over_under_2_5
from app.data_ingestion import run_ingestion
from app.scheduler import start_scheduler
```

### New Imports
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

## Updated Files

### Application Code
- ✅ All imports in `app/` updated to use new structure
- ✅ All relative imports updated

### External Files
- ✅ `alembic/env.py` - Updated imports
- ✅ `Dockerfile` - Updated uvicorn command
- ✅ `scripts/validate_quickstart.py` - Updated imports
- ✅ `tests/` - All test files updated

### Documentation
- ✅ `app/STRUCTURE.md` - Created structure documentation

## Backward Compatibility

The main app can still be imported as:
```python
from app import app  # Works via app/__init__.py
```

However, for explicit imports, use the new structure:
```python
from app.api.main import app
```

## Command Updates

### Docker
```bash
# Old
uvicorn app.main:app

# New
uvicorn app.api.main:app
```

### Training Scripts
```bash
# Old
python -m app.train_match

# New (still works, module path unchanged)
python -m app.ml.train_match
```

## Testing

All imports have been updated. The structure is ready for use. Linter warnings about unresolved imports are expected if dependencies aren't installed in the linting environment.

