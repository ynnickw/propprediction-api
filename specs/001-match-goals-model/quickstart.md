# Quickstart: Match-Level Goals Prediction Models

**Feature**: Match-Level Goals Prediction Models  
**Date**: 2025-11-27  
**Purpose**: Testing scenarios and validation steps for match-level predictions

## Prerequisites

- Docker and Docker Compose running
- Supabase local instance running
- Historical data files available (D1_2020-2025.csv, player_stats_history_enriched.csv)
- API keys configured (API_FOOTBALL_KEY, THE_ODDS_API_KEY)

## Setup Steps

1. **Start services**:
   ```bash
   supabase start
   docker-compose up --build
   ```

2. **Run database migrations**:
   ```bash
   docker-compose run --rm backend alembic upgrade head
   ```

3. **Verify data availability**:
   ```bash
   # Check that historical match data exists
   ls -la data/D1_*.csv
   
   # Check that player data exists
   ls -la data/player_stats_history_enriched.csv
   ```

## Testing Scenarios

### Scenario 1: Train Over/Under 2.5 Goals Model

**Goal**: Verify that the model training process successfully creates model files.

**Steps**:
1. Run training script:
   ```bash
   docker-compose run --rm backend python -m app.train_match --prop-type over_under_2.5
   ```

2. **Expected Results**:
   - Model files created in `models/`:
     - `lgbm_over_under_2.5.txt`
     - `poisson_over_under_2.5.joblib`
   - Training logs show feature importance rankings
   - Model performance metrics printed (accuracy, precision, recall)
   - Feature-engineered dataset saved to `data/match_features_over_under_2.5.csv`

3. **Validation**:
   - Check model files exist and are non-empty
   - Verify accuracy >= 55% (SC-001)
   - Check feature importance shows top 10 features (SC-009)

### Scenario 2: Train BTTS Model

**Goal**: Verify that the BTTS model training process works correctly.

**Steps**:
1. Run training script:
   ```bash
   docker-compose run --rm backend python -m app.train_match --prop-type btts
   ```

2. **Expected Results**:
   - Model files created:
     - `lgbm_btts.txt`
     - `poisson_btts.joblib`
   - Training logs show feature importance
   - Model performance metrics printed
   - Feature-engineered dataset saved to `data/match_features_btts.csv`

3. **Validation**:
   - Check model files exist and are non-empty
   - Verify accuracy >= 60% (SC-002)
   - Check feature importance shows top 10 features (SC-009)

### Scenario 3: Generate Match Predictions (Manual)

**Goal**: Test prediction generation for upcoming matches without running full pipeline.

**Steps**:
1. Ensure upcoming matches exist in database (run data ingestion if needed):
   ```bash
   docker-compose run --rm backend python -c "from app.data_ingestion import run_ingestion; import asyncio; asyncio.run(run_ingestion())"
   ```

2. Run prediction script:
   ```bash
   docker-compose run --rm backend python -m app.match_predictions --match-id <match_id>
   ```

3. **Expected Results**:
   - Predictions generated for Over/Under 2.5 and BTTS
   - Edge percentages calculated
   - Picks with edge >= 8% stored in database
   - Logs show prediction details

4. **Validation**:
   - Check database for DailyPick records with prediction_type in ['over_under_2.5', 'btts']
   - Verify edge_percent >= 8% for stored picks
   - Verify model_prob and bookmaker_prob are between 0 and 1

### Scenario 4: Full Pipeline Integration

**Goal**: Verify that match predictions are integrated into daily pipeline.

**Steps**:
1. Trigger pipeline manually:
   ```bash
   docker-compose run --rm backend python -c "from app.scheduler import pipeline_job; import asyncio; asyncio.run(pipeline_job())"
   ```

2. **Expected Results**:
   - Data ingestion runs (matches and odds fetched)
   - Player prop predictions generated (existing functionality)
   - Match predictions generated for all upcoming matches
   - Picks stored in database
   - Pipeline completes within 5 minutes (SC-004)

3. **Validation**:
   - Check logs show match prediction steps
   - Verify picks created for matches within 48 hours
   - Verify no duplicate picks for same match and prediction_type
   - Check pipeline completion time < 5 minutes

### Scenario 5: API Endpoint Testing

**Goal**: Verify API endpoints return match-level picks correctly.

**Steps**:
1. Ensure picks exist in database (run Scenario 4 first)

2. Test `/picks` endpoint with filtering:
   ```bash
   curl -H "X-API-Key: your-api-key" \
     "http://localhost:8000/picks?prediction_type=over_under_2.5"
   ```

3. Test `/picks/match` endpoint:
   ```bash
   curl -H "X-API-Key: your-api-key" \
     "http://localhost:8000/picks/match?min_edge=8"
   ```

4. **Expected Results**:
   - `/picks` returns all picks, filterable by prediction_type
   - `/picks/match` returns only match-level picks
   - Response time < 2 seconds (SC-007)
   - Response matches PickResponse or MatchPickResponse schema

5. **Validation**:
   - Verify response structure matches OpenAPI schema
   - Check that player_name is null for match-level picks
   - Verify prediction_type field is present
   - Test filtering works correctly

### Scenario 6: Feature Engineering Validation

**Goal**: Verify feature engineering produces correct team-level features.

**Steps**:
1. Run feature engineering test:
   ```bash
   docker-compose run --rm backend python -m pytest tests/unit/test_match_features.py -v
   ```

2. **Expected Results**:
   - Features computed correctly (rolling averages, head-to-head, etc.)
   - Missing data handled with defaults
   - Time-based splitting prevents data leakage
   - Feature importance analysis identifies top features

3. **Validation**:
   - All unit tests pass
   - Feature distributions are reasonable (no extreme outliers)
   - Feature importance shows top 5 features account for >= 60% importance (SC-009)

### Scenario 7: Backtesting Validation

**Goal**: Verify model performance on historical data.

**Steps**:
1. Run backtesting:
   ```bash
   docker-compose run --rm backend python -m app.backtest_match_models --season 2023-2024
   ```

2. **Expected Results**:
   - Backtesting results for Over/Under 2.5 (accuracy >= 55%)
   - Backtesting results for BTTS (accuracy >= 60%)
   - Expected value calculations show positive EV for picks with 8%+ edge
   - Performance metrics logged

3. **Validation**:
   - Over/Under 2.5 accuracy >= 55% (SC-001)
   - BTTS accuracy >= 60% (SC-002)
   - Positive expected value for 8%+ edge picks over 30-day period (SC-005)

### Scenario 8: Edge Cases

**Goal**: Verify system handles edge cases gracefully.

**Test Cases**:
1. **Missing team statistics**: Match with newly promoted team (limited history)
   - Expected: System uses defaults (league averages) or skips prediction with log

2. **Missing odds**: Match without bookmaker odds
   - Expected: System skips edge calculation, logs warning, may still generate prediction

3. **Duplicate prevention**: Pipeline runs twice for same match
   - Expected: No duplicate picks created (unique constraint or upsert logic)

4. **No upcoming matches**: Pipeline runs when no matches in next 48 hours
   - Expected: Pipeline completes successfully with log message, no errors

5. **Model file missing**: Prediction attempted without trained models
   - Expected: Error logged, prediction skipped, graceful failure

## Success Criteria Validation

- ✅ **SC-001**: Over/Under 2.5 accuracy >= 55% (validated in Scenario 7)
- ✅ **SC-002**: BTTS accuracy >= 60% (validated in Scenario 7)
- ✅ **SC-003**: 90%+ match coverage (validated in Scenario 4)
- ✅ **SC-004**: Pipeline completes in < 5 minutes (validated in Scenario 4)
- ✅ **SC-005**: Positive EV for 8%+ edge picks (validated in Scenario 7)
- ✅ **SC-006**: Integration doesn't disrupt player props (validated in Scenario 4)
- ✅ **SC-007**: API response time < 2 seconds (validated in Scenario 5)
- ✅ **SC-008**: Model training completes successfully (validated in Scenarios 1-2)
- ✅ **SC-009**: Feature importance identifies top features (validated in Scenarios 1-2, 6)

## Troubleshooting

**Issue**: Model training fails with "FileNotFoundError"
- **Solution**: Ensure data files exist in `data/` directory, run data preparation script first

**Issue**: Predictions return null/empty results
- **Solution**: Check that matches exist in database with status='NS', verify team statistics are available

**Issue**: API returns 401 Unauthorized
- **Solution**: Verify API key is set in environment and passed in X-API-Key header

**Issue**: Pipeline takes longer than 5 minutes
- **Solution**: Check database query performance, consider adding indexes, verify team stats caching works

