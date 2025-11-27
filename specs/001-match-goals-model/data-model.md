# Data Model: Match-Level Goals Prediction Models

**Feature**: Match-Level Goals Prediction Models  
**Date**: 2025-11-27  
**Phase**: 1 - Design & Contracts

## Entities

### Match (Existing - Extended)

**Purpose**: Represents a football match fixture with teams, timing, and odds.

**Fields**:
- `id` (Integer, PK): Primary key
- `fixture_id` (Integer, Unique): External API fixture identifier
- `league_id` (Integer): League identifier (78 for Bundesliga)
- `home_team` (String): Home team name
- `away_team` (String): Away team name
- `start_time` (DateTime): Match start time
- `status` (String): Match status (NS, FT, etc.)
- `odds_home` (Float, Nullable): Bookmaker odds for home win (1x2)
- `odds_draw` (Float, Nullable): Bookmaker odds for draw (1x2)
- `odds_away` (Float, Nullable): Bookmaker odds for away win (1x2)
- `odds_over_2_5` (Float, Nullable): **NEW** - Bookmaker odds for Over 2.5 goals
- `odds_under_2_5` (Float, Nullable): **NEW** - Bookmaker odds for Under 2.5 goals
- `odds_btts_yes` (Float, Nullable): **NEW** - Bookmaker odds for Both Teams To Score Yes
- `odds_btts_no` (Float, Nullable): **NEW** - Bookmaker odds for Both Teams To Score No

**Relationships**:
- One-to-many with `PropLine` (existing)
- One-to-many with `DailyPick` (existing, extended)

**Validation Rules**:
- `home_team` and `away_team` must be different
- `start_time` must be in the future for upcoming matches
- Odds values must be > 1.0 if provided
- `status` must be one of: NS (Not Started), FT (Full Time), etc.

**State Transitions**: N/A (status field tracks match state)

### DailyPick (Existing - Extended)

**Purpose**: Represents a daily pick recommendation, now supporting both player props and match-level predictions.

**Fields**:
- `id` (Integer, PK): Primary key
- `player_id` (Integer, FK, Nullable): **MODIFIED** - Foreign key to Player (nullable for match-level picks)
- `match_id` (Integer, FK): Foreign key to Match
- `prediction_type` (String): **NEW** - Type of prediction: 'player_prop', 'over_under_2.5', 'btts'
- `prop_type` (String): Prop type (e.g., 'shots', 'goals', 'over_under_2.5', 'btts')
- `line` (Float): Line value (e.g., 2.5 for Over/Under, N/A for BTTS)
- `recommendation` (String): Recommendation ('Over', 'Under', 'Yes', 'No')
- `model_expected` (Float): Model's expected value
- `bookmaker_prob` (Float): Bookmaker's implied probability
- `model_prob` (Float): Model's predicted probability
- `edge_percent` (Float): Calculated edge percentage (model_prob - bookmaker_prob)
- `confidence` (String): Confidence level ('High', 'Medium', 'Low')
- `created_at` (DateTime): Timestamp when pick was created

**Relationships**:
- Many-to-one with `Match` (existing)
- Many-to-one with `Player` (existing, now optional)

**Validation Rules**:
- `prediction_type` must be one of: 'player_prop', 'over_under_2.5', 'btts'
- If `prediction_type` is 'player_prop', `player_id` must not be null
- If `prediction_type` is 'over_under_2.5' or 'btts', `player_id` must be null
- `edge_percent` must be >= 0 (only positive edges stored)
- `model_prob` and `bookmaker_prob` must be between 0 and 1
- `recommendation` must match prediction_type: 'Over'/'Under' for over_under_2.5, 'Yes'/'No' for btts

**State Transitions**: N/A (immutable once created)

### TeamMatchFeatures (In-Memory/Computed)

**Purpose**: Represents aggregated features for a team in a specific match context. Not persisted to database, computed on-demand during prediction.

**Fields**:
- `team_name` (String): Team identifier
- `opponent_name` (String): Opponent identifier
- `is_home` (Boolean): Whether team is playing at home
- `match_date` (Date): Date of the match
- `goals_scored_avg_season` (Float): Average goals scored per match (season)
- `goals_scored_avg_last_5` (Float): Average goals scored in last 5 matches
- `goals_scored_avg_last_10` (Float): Average goals scored in last 10 matches
- `goals_scored_avg_home` (Float): Average goals scored at home (season)
- `goals_scored_avg_away` (Float): Average goals scored away (season)
- `goals_conceded_avg_season` (Float): Average goals conceded per match (season)
- `goals_conceded_avg_last_5` (Float): Average goals conceded in last 5 matches
- `goals_conceded_avg_last_10` (Float): Average goals conceded in last 10 matches
- `goals_conceded_avg_home` (Float): Average goals conceded at home (season)
- `goals_conceded_avg_away` (Float): Average goals conceded away (season)
- `shots_avg_season` (Float): Average shots per match (season)
- `shots_on_target_avg_season` (Float): Average shots on target per match (season)
- `shots_conceded_avg_season` (Float): Average shots conceded per match (season)
- `scoring_rate_season` (Float): Percentage of matches where team scored (season)
- `scoring_rate_last_5` (Float): Percentage of matches where team scored (last 5)
- `conceding_rate_season` (Float): Percentage of matches where team conceded (season)
- `conceding_rate_last_5` (Float): Percentage of matches where team conceded (last 5)
- `btts_rate_season` (Float): Percentage of matches where both teams scored (season, team perspective)
- `head_to_head_total_goals_avg` (Float): Average total goals in last 5 head-to-head meetings
- `head_to_head_btts_rate` (Float): Percentage of last 5 head-to-head where both teams scored
- `days_since_last_match` (Integer): Days since team's last match
- `recent_form_goals_scored` (List[Float]): Goals scored in last 5 matches
- `recent_form_goals_conceded` (List[Float]): Goals conceded in last 5 matches

**Relationships**: N/A (computed entity)

**Validation Rules**:
- All averages must be >= 0
- Rates must be between 0 and 1
- Lists must have length <= 5

### MatchPredictionModel (File-Based)

**Purpose**: Represents a trained machine learning model stored on disk.

**Attributes** (not database fields, metadata):
- `model_type` (String): 'over_under_2.5' or 'btts'
- `algorithm` (String): 'lightgbm' or 'poisson'
- `file_path` (String): Path to model file (e.g., 'models/lgbm_over_under_2.5.txt')
- `training_date` (DateTime): Date when model was trained
- `version` (String): Model version identifier
- `performance_metrics` (Dict): Accuracy, precision, recall, expected value from backtesting
- `feature_list` (List[String]): List of features used in training
- `feature_importance` (Dict): Feature importance rankings

**Storage**: Files in `models/` directory, metadata could be stored in database (optional)

**Validation Rules**:
- Model files must exist at specified paths
- Feature lists must match features used in prediction
- Performance metrics must be from backtesting on held-out data

## Data Flow

### Training Data Preparation

1. Load historical match data from D1_*.csv files (5 years)
2. Load player-level data from player_stats_history_enriched.csv
3. Aggregate player statistics by team and match date
4. Merge match-level and aggregated player data
5. Engineer features (rolling averages, head-to-head, etc.)
6. Create target variables:
   - Over/Under 2.5: Binary (1 if total_goals > 2.5, else 0)
   - BTTS: Binary (1 if both teams scored, else 0)
7. Split data temporally (train on older data, validate on recent data)
8. Export feature-engineered dataset for training

### Prediction Flow

1. Fetch upcoming matches from database (status = 'NS', start_time within 48 hours)
2. For each match:
   a. Fetch team statistics from historical data
   b. Compute TeamMatchFeatures for home and away teams
   c. Load trained models (LightGBM + Poisson for each prediction type)
   d. Generate features DataFrame
   e. Run model predictions (ensemble)
   f. Fetch bookmaker odds from Match table
   g. Calculate edge percentage
   h. If edge >= threshold (8%), create DailyPick record
3. Store picks in database
4. Return picks via API

## Database Migrations Required

### Migration 1: Extend Match Table

```sql
ALTER TABLE matches 
ADD COLUMN odds_over_2_5 FLOAT,
ADD COLUMN odds_under_2_5 FLOAT,
ADD COLUMN odds_btts_yes FLOAT,
ADD COLUMN odds_btts_no FLOAT;
```

### Migration 2: Extend DailyPick Table

```sql
ALTER TABLE daily_picks 
ALTER COLUMN player_id DROP NOT NULL,
ADD COLUMN prediction_type VARCHAR(50) NOT NULL DEFAULT 'player_prop';

-- Add constraint
ALTER TABLE daily_picks 
ADD CONSTRAINT chk_prediction_type 
CHECK (prediction_type IN ('player_prop', 'over_under_2.5', 'btts'));

-- Add constraint for player_id based on prediction_type
ALTER TABLE daily_picks 
ADD CONSTRAINT chk_player_id_for_prediction_type 
CHECK (
  (prediction_type = 'player_prop' AND player_id IS NOT NULL) OR
  (prediction_type IN ('over_under_2.5', 'btts') AND player_id IS NULL)
);
```

## Data Quality Constraints

- Match odds must be > 1.0 if provided
- Model probabilities must be between 0 and 1
- Edge percentages must be >= 0 (only positive edges stored)
- Team statistics must be computed from at least 5 historical matches when available
- Missing features handled with defaults (season averages, league averages)
- Duplicate picks prevented by unique constraint on (match_id, prediction_type, prop_type, created_at date)

