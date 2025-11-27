# Implementation Plan: Match-Level Goals Prediction Models

**Branch**: `001-match-goals-model` | **Date**: 2025-11-27 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-match-goals-model/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Train and deploy machine learning models for match-level predictions (Over/Under 2.5 goals and Both Teams To Score) using historical Bundesliga data. Models will use ensemble approach (LightGBM + Poisson) similar to existing player prop models, with comprehensive feature engineering from team-level statistics aggregated from player data and match-level datasets. Predictions will be integrated into the existing daily pipeline to generate and store match-level picks alongside player prop picks.

## Technical Context

**Language/Version**: Python 3.14 (as indicated by venv structure)  
**Primary Dependencies**: FastAPI, LightGBM, scikit-learn, pandas, SQLAlchemy, Alembic, APScheduler, structlog  
**Storage**: PostgreSQL via Supabase, model files stored in `models/` directory  
**Testing**: pytest, pytest-asyncio for async tests  
**Target Platform**: Linux server (Docker containers)  
**Project Type**: Single backend API service  
**Performance Goals**: Pipeline completes match predictions for 5-10 matches within 5 minutes; API responses under 2 seconds  
**Constraints**: Must integrate with existing player prop prediction pipeline without disruption; API rate limits (7500 requests/day for football-api); model training must be reproducible with fixed random seeds  
**Scale/Scope**: Predictions for all Bundesliga matches within 48-hour window (typically 5-10 matches per day); historical training data spans 5 years of Bundesliga matches

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### I. API-First Design
✅ **PASS**: Match-level picks will be exposed through existing `/picks` endpoint with filtering, or new dedicated endpoints. API contracts will be documented via OpenAPI/Swagger. Business logic separated from API layer.

### II. Data Quality & Validation (NON-NEGOTIABLE)
✅ **PASS**: All external data (match data, odds) will be validated before persistence. Missing data handled gracefully with defaults or explicit errors. Data transformations will be idempotent. Database constraints enforce referential integrity.

### III. Model Versioning & Reproducibility
✅ **PASS**: Models stored in `models/` directory with descriptive filenames (e.g., `lgbm_over_under_2.5.txt`, `poisson_btts.joblib`). Training scripts will use fixed random seeds, dependencies pinned in requirements.txt. Model performance metrics logged and tracked.

### IV. Observability & Logging
✅ **PASS**: All prediction operations, model training, and errors will emit structured logs via structlog. Logs include request IDs, timestamps, and sufficient context. Health check endpoints already exist.

### V. Testing Discipline
✅ **PASS**: Unit tests for feature engineering and model inference. Integration tests for API endpoints and pipeline execution. Contract tests for API response schemas. Tests runnable in Docker and CI/CD.

**GATE RESULT**: ✅ **ALL GATES PASS** - No violations. Proceed to Phase 0 research.

### Post-Phase 1 Re-evaluation

After Phase 1 design completion, all constitution gates remain PASS. Design artifacts (data-model.md, contracts/, quickstart.md) comply with all principles:
- **API-First Design**: API contracts follow RESTful conventions with OpenAPI documentation in `contracts/match-picks-api.yaml`
- **Data Quality & Validation**: Data model includes validation rules, constraints, and graceful handling of missing data
- **Model Versioning & Reproducibility**: Model storage and versioning documented in data model and project structure
- **Observability & Logging**: Logging requirements addressed in quickstart testing scenarios
- **Testing Discipline**: Quickstart includes unit, integration, and contract test scenarios

**GATE RESULT (Post-Phase 1)**: ✅ **ALL GATES PASS** - Design artifacts comply with constitution.

## Project Structure

### Documentation (this feature)

```text
specs/001-match-goals-model/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
app/
├── train.py                    # Existing player prop training (extend for match models)
├── train_match.py              # NEW: Match-level model training script
├── model.py                    # Existing ensemble model (extend for match predictions)
├── match_features.py           # NEW: Feature engineering for match-level predictions
├── match_predictions.py        # NEW: Match prediction logic and edge calculation
├── scheduler.py                # Existing pipeline (extend to include match predictions)
├── main.py                     # Existing API (extend endpoints if needed)
├── models.py                   # Existing DB models (extend DailyPick or add MatchPick)
├── schemas.py                  # Existing Pydantic schemas (extend for match picks)
├── data_ingestion.py           # Existing data ingestion (may need match odds ingestion)
└── features.py                 # Existing player features (reference for patterns)

models/
├── lgbm_over_under_2.5.txt     # NEW: LightGBM model for Over/Under 2.5
├── poisson_over_under_2.5.joblib  # NEW: Poisson model for Over/Under 2.5
├── lgbm_btts.txt               # NEW: LightGBM model for BTTS
└── poisson_btts.joblib        # NEW: Poisson model for BTTS

data/
├── D1_2020.csv through D1_2025.csv  # Existing match-level datasets
├── player_stats_history_enriched.csv  # Existing player-level data
└── match_features_dataset.csv        # NEW: Feature-engineered match dataset

tests/
├── unit/
│   ├── test_match_features.py        # NEW: Unit tests for feature engineering
│   └── test_match_predictions.py     # NEW: Unit tests for predictions
├── integration/
│   ├── test_match_pipeline.py        # NEW: Integration tests for pipeline
│   └── test_match_api.py             # NEW: Integration tests for API
└── contract/
    └── test_match_picks_schema.py    # NEW: Contract tests for API schemas
```

**Structure Decision**: Single project structure maintained. New modules added to `app/` directory following existing patterns. Match prediction functionality extends existing architecture without requiring new services or major restructuring.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations - all constitution gates pass.
