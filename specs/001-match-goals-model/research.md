# Research: Match-Level Goals Prediction Models

**Feature**: Match-Level Goals Prediction Models  
**Date**: 2025-11-27  
**Phase**: 0 - Outline & Research

## Research Tasks & Findings

### 1. Feature Engineering for Match-Level Predictions

**Task**: Research best practices for aggregating player-level statistics to team-level features for match predictions.

**Decision**: Use rolling window aggregations (last 5, 10 matches) with proper time-based splitting to avoid data leakage. Aggregate player statistics by team using sums (for goals, shots) and averages (for rates, percentages).

**Rationale**: 
- Rolling windows capture recent form while maintaining sufficient sample size
- Time-based splitting ensures training data only uses information available at prediction time
- Team-level aggregations (sums for counts, averages for rates) align with football analytics best practices

**Alternatives Considered**:
- Season-long averages: Rejected - too static, doesn't capture form
- Weighted averages by player minutes: Considered but adds complexity; simple team aggregates sufficient for initial model
- Advanced metrics (xG, xGA): Preferred if available from API, but not required for MVP

**Implementation Notes**:
- Use pandas groupby operations to aggregate player stats by team and match date
- Create features for both home and away team perspectives
- Include home/away splits for teams (home performance often differs from away)

### 2. Data Aggregation from Multiple Sources

**Task**: Determine how to combine player-level data (player_stats_history_enriched.csv) with match-level data (D1_2020-2025.csv).

**Decision**: Use match-level datasets (D1_*.csv) as primary source for historical match outcomes and team statistics. Aggregate player-level data to supplement team statistics (goals, shots) when match-level data is incomplete. Use match-level data for head-to-head history and historical odds.

**Rationale**:
- Match-level datasets already contain aggregated team statistics (HS, AS, HST, AST, goals)
- Player-level data provides granular statistics that can be aggregated when needed
- Combining both sources provides redundancy and completeness

**Alternatives Considered**:
- Player-level only: Rejected - requires extensive aggregation, match-level data already aggregated
- Match-level only: Considered but player data provides additional features (player form, team composition)

**Implementation Notes**:
- Primary: Load D1_*.csv files, extract team stats per match
- Secondary: Aggregate player_stats_history_enriched.csv by team and date
- Merge on match date, home_team, away_team
- Handle missing data with forward fill or default values

### 3. Model Architecture for Binary Classification

**Task**: Determine model architecture for Over/Under 2.5 (binary classification) and BTTS (binary classification).

**Decision**: Use ensemble approach (LightGBM + Poisson Regression) similar to existing player prop models. LightGBM for capturing complex feature interactions, Poisson for theoretically sound goal distribution modeling.

**Rationale**:
- Consistency with existing player prop models reduces maintenance overhead
- LightGBM handles non-linear relationships and feature interactions well
- Poisson regression aligns with goal distribution theory (goals are count data)
- Ensemble approach combines strengths of both models

**Alternatives Considered**:
- LightGBM only: Considered but Poisson adds theoretical foundation
- Neural networks: Rejected - overkill for this problem, harder to interpret
- Logistic regression: Considered but LightGBM captures more complex patterns

**Implementation Notes**:
- Use same ensemble weighting strategy as player props (context-aware weights)
- For Over/Under 2.5: Binary classification (Over = 1, Under = 0)
- For BTTS: Binary classification (Yes = 1, No = 0)
- Use probability outputs from both models, average with weights

### 4. Database Schema for Match-Level Picks

**Task**: Determine how to store match-level picks while maintaining consistency with existing DailyPick schema.

**Decision**: Extend existing DailyPick table to support match-level picks by making player_id nullable and adding a prediction_type field to distinguish match-level from player-level picks. Alternative: Create separate MatchPick table if schema changes become too complex.

**Rationale**:
- Reusing DailyPick maintains API consistency and reduces code duplication
- Nullable player_id allows match-level picks (no player association)
- prediction_type field clearly distinguishes pick types
- If schema becomes too complex, separate table is cleaner but requires more API changes

**Alternatives Considered**:
- Separate MatchPick table: Considered - cleaner separation but requires new API endpoints
- Completely new schema: Rejected - breaks existing API contracts

**Implementation Notes**:
- Add migration to make player_id nullable in DailyPick
- Add prediction_type field (values: 'player_prop', 'over_under_2.5', 'btts')
- Update schemas.py to handle nullable player_id
- Update API endpoints to filter by prediction_type

### 5. Feature Importance Analysis Approach

**Task**: Determine methodology for feature importance analysis and feature selection.

**Decision**: Use LightGBM built-in feature importance (gain-based) as primary metric, supplemented with SHAP values for interpretability. Test multiple feature sets iteratively, comparing model performance metrics (accuracy, precision, recall, expected value).

**Rationale**:
- LightGBM feature importance is fast and built-in
- SHAP values provide model-agnostic interpretability
- Iterative testing allows data-driven feature selection
- Expected value metric ensures features improve betting edge, not just accuracy

**Alternatives Considered**:
- Permutation importance only: Considered but slower, LightGBM importance sufficient
- Correlation analysis only: Rejected - correlation doesn't capture non-linear relationships
- Manual feature selection: Rejected - data-driven approach more objective

**Implementation Notes**:
- Train initial model with comprehensive feature set
- Extract feature importance rankings
- Iteratively remove low-importance features, retrain, compare metrics
- Document final feature set with importance rankings and rationale

### 6. Odds Data Integration

**Task**: Determine how to ingest and use bookmaker odds for Over/Under 2.5 and BTTS markets.

**Decision**: Extend existing odds ingestion (currently fetches 1x2 odds) to include Over/Under 2.5 and BTTS odds from The Odds API. Store odds in Match table or new MatchOdds table. Use odds as features in training and for edge calculation in predictions.

**Rationale**:
- The Odds API already integrated, just need to fetch additional markets
- Odds are strong predictors (market sentiment) and essential for edge calculation
- Storing odds allows historical analysis and backtesting

**Alternatives Considered**:
- Manual odds entry: Rejected - not scalable, error-prone
- Scraping odds: Rejected - unreliable, violates terms of service
- Using only historical odds from D1_*.csv: Considered but current odds needed for live predictions

**Implementation Notes**:
- Extend data_ingestion.py to fetch Over/Under 2.5 and BTTS odds
- Store in database (extend Match table or create MatchOdds table)
- Use odds as features: implied probabilities, odds ratios
- Calculate edge: model_probability vs. bookmaker_implied_probability

### 7. Pipeline Integration Strategy

**Task**: Determine how to integrate match predictions into existing daily pipeline without disrupting player prop predictions.

**Decision**: Add match prediction step to existing pipeline_job() function after player prop predictions complete. Use same error handling and logging patterns. Cache team statistics to avoid redundant database queries.

**Rationale**:
- Sequential execution ensures player props complete first (existing functionality preserved)
- Shared error handling and logging maintains consistency
- Caching improves performance for multiple match predictions

**Alternatives Considered**:
- Separate pipeline job: Considered but adds complexity, sequential execution sufficient
- Parallel execution: Considered but adds complexity, sequential is simpler and sufficient
- Completely separate service: Rejected - overkill, same data sources and models

**Implementation Notes**:
- Extend scheduler.py pipeline_job() function
- Add match prediction step after player prop predictions
- Reuse team_stats_cache from player props if applicable
- Use same transaction management and error handling

## Resolved Clarifications

All technical context items are resolved. No NEEDS CLARIFICATION markers remain.

## Next Steps

Proceed to Phase 1: Design & Contracts
- Create data-model.md with entity definitions
- Generate API contracts for match pick endpoints
- Create quickstart.md with testing scenarios

