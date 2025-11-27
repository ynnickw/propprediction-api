# Feature Specification: Match-Level Goals Prediction Models

**Feature Branch**: `001-match-goals-model`  
**Created**: 2025-11-27  
**Status**: Draft  
**Input**: User description: "train a new model that doesnt focus on player level but more on amount of goals that will be scored in the game (e.g over/under 2.5 ) and if both team score. i have a large dataset of all bundesliga games of the last 5 years with columns: fixture_id,date,player_id,player_name,team,opponent,is_home,position,minutes,rating,shots,shots_on_target,goals,assists,passes,passes_accurate,key_passes,tackles,blocks,interceptions,duels_total,duels_won,dribbles_attempts,dribbles_success,fouls_drawn,fouls_committed,yellow_cards,red_cards,cards,HS,AS,HST,AST,HC,AC,HF,AF,HY,AY,HR,AR,B365H,B365D,B365A but it is player specifi. i also have a dataset of bundesliga stats mor eon game level: D1_2025.csv. i also have access to football-api (7500 request/day) if we need more data to train the model. in the end i want to have a similar logic to the current prediction that runs a pipeline everyday and returns daily picks"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Over/Under 2.5 Goals Prediction Model (Priority: P1)

Users need predictions for whether a match will have over or under 2.5 total goals scored. The system must train a machine learning model using historical Bundesliga match data, generate predictions for upcoming matches, calculate value edges against bookmaker odds, and provide daily picks with confidence levels.

**Why this priority**: This is the primary match-level prediction type requested and can deliver value independently. Over/Under 2.5 goals is a fundamental betting market with clear success criteria (total goals > 2.5 or <= 2.5).

**Independent Test**: Can be fully tested by training the model on historical data, generating predictions for a set of upcoming matches, and verifying that predictions include expected value calculations and edge percentages. The model can be evaluated independently using historical backtesting before integration into the daily pipeline.

**Acceptance Scenarios**:

1. **Given** historical Bundesliga match data from the last 5 years, **When** the training process runs, **Then** the system produces a trained model file that can predict over/under 2.5 goals probability for new matches
2. **Given** an upcoming match with team statistics and bookmaker odds, **When** the prediction system processes the match, **Then** it returns a prediction (Over/Under) with model probability, bookmaker probability, and calculated edge percentage
3. **Given** predictions for multiple upcoming matches, **When** the system filters picks by minimum edge threshold (e.g., 8%), **Then** it returns only matches where the model identifies value opportunities
4. **Given** a trained model and historical matches, **When** backtesting is performed, **Then** the system reports model accuracy metrics and expected value performance

---

### User Story 2 - Both Teams To Score (BTTS) Prediction Model (Priority: P2)

Users need predictions for whether both teams will score at least one goal in a match. The system must train a separate machine learning model using historical Bundesliga match data, generate BTTS predictions for upcoming matches, calculate value edges against bookmaker odds, and provide daily picks.

**Why this priority**: BTTS is the second requested prediction type and can operate independently from Over/Under predictions. It provides additional value opportunities for users.

**Independent Test**: Can be fully tested by training the model on historical data where the target is whether both teams scored (binary classification), generating predictions for upcoming matches, and verifying that predictions include expected value calculations. The model can be evaluated independently using historical backtesting.

**Acceptance Scenarios**:

1. **Given** historical Bundesliga match data from the last 5 years, **When** the training process runs for BTTS, **Then** the system produces a trained model file that can predict BTTS probability (Yes/No) for new matches
2. **Given** an upcoming match with team statistics and bookmaker BTTS odds, **When** the prediction system processes the match, **Then** it returns a BTTS prediction (Yes/No) with model probability, bookmaker probability, and calculated edge percentage
3. **Given** predictions for multiple upcoming matches, **When** the system filters picks by minimum edge threshold, **Then** it returns only matches where the model identifies BTTS value opportunities
4. **Given** a trained BTTS model and historical matches, **When** backtesting is performed, **Then** the system reports model accuracy, precision, recall, and expected value performance

---

### User Story 3 - Daily Pipeline Integration for Match Predictions (Priority: P3)

Users need match-level predictions integrated into the existing daily pipeline so that picks are automatically generated, stored, and accessible via the API alongside player-level picks. The system must run predictions daily, calculate edges, filter by minimum thresholds, and store results in a format consistent with the current DailyPick structure.

**Why this priority**: Integration enables automated daily delivery of match predictions, matching the workflow users expect from the existing player prop prediction system. This story depends on User Stories 1 and 2 being complete.

**Independent Test**: Can be fully tested by running the daily pipeline job, verifying that match predictions are generated for upcoming matches, checking that picks are stored in the database with correct structure, and confirming that picks are accessible via the existing API endpoints (or new endpoints if needed).

**Acceptance Scenarios**:

1. **Given** the daily pipeline is scheduled to run, **When** it executes, **Then** it generates Over/Under 2.5 and BTTS predictions for all upcoming Bundesliga matches within the next 48 hours
2. **Given** predictions have been generated, **When** the system calculates edges and applies minimum threshold filtering (e.g., 8% edge), **Then** only matches with sufficient value are stored as DailyPick records
3. **Given** match-level picks have been stored, **When** users query the picks API endpoint, **Then** they receive match predictions alongside player prop predictions, with clear distinction between prediction types
4. **Given** the pipeline runs daily, **When** new matches become available or odds change, **Then** the system updates predictions and picks accordingly, avoiding duplicate entries for the same match and prediction type

---

### Edge Cases

- What happens when historical match data is missing for one or both teams in an upcoming match?
- How does the system handle matches where bookmaker odds are not available or incomplete?
- What happens when the model confidence is very low (e.g., < 50% probability) but edge calculation suggests value?
- How does the system handle matches with incomplete team statistics (e.g., newly promoted teams with limited historical data)?
- What happens when the daily pipeline runs but no upcoming matches are found in the next 48 hours?
- How does the system handle model training failures or prediction errors for individual matches?
- What happens when bookmaker odds change between pipeline runs for the same match?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST train machine learning models for Over/Under 2.5 goals prediction using historical Bundesliga match data from the last 5 years
- **FR-002**: System MUST train machine learning models for Both Teams To Score (BTTS) prediction using historical Bundesliga match data from the last 5 years
- **FR-003**: System MUST aggregate player-level statistics to team-level features for match predictions (e.g., team average goals scored, team average goals conceded, recent form)
- **FR-004**: System MUST extract match-level features from game-level datasets (D1_2025.csv and similar files) including team statistics, head-to-head records, and historical match outcomes
- **FR-005**: System MUST generate features that include team offensive statistics (goals scored, shots, shots on target), defensive statistics (goals conceded, shots allowed), recent form (last 5-10 matches), and head-to-head history
- **FR-005a**: System MUST research and validate which features have the highest predictive power for Over/Under 2.5 goals and BTTS predictions through feature importance analysis, correlation studies, and iterative model testing
- **FR-005b**: System MUST test and compare feature sets including but not limited to: team goals scored/conceded averages (season, last 5/10 matches, home/away splits), team shots/shots on target statistics, team expected goals (xG) if available, recent form trends, head-to-head goal history, home/away performance differentials, team strength ratings, bookmaker odds and market sentiment, fixture difficulty ratings, and time-based features (days since last match, fixture congestion)
- **FR-005c**: System MUST document feature importance rankings for each model type (Over/Under 2.5 and BTTS) and use this analysis to optimize feature selection and engineering
- **FR-006**: System MUST incorporate bookmaker odds as features in model training and use current odds for edge calculation in predictions
- **FR-007**: System MUST calculate expected value and edge percentage by comparing model probability to bookmaker implied probability for each prediction type
- **FR-008**: System MUST filter predictions to only include picks with edge percentage above a configurable minimum threshold (default: 8%)
- **FR-009**: System MUST store match-level predictions in a database structure that distinguishes them from player-level predictions while maintaining consistency with existing DailyPick schema
- **FR-010**: System MUST integrate match prediction generation into the existing daily scheduled pipeline that runs automatically
- **FR-011**: System MUST generate predictions for all upcoming Bundesliga matches within the next 48 hours during each pipeline run
- **FR-012**: System MUST handle missing or incomplete data gracefully by using default values or skipping predictions when critical features are unavailable
- **FR-013**: System MUST support model versioning and storage in the models/ directory with descriptive filenames
- **FR-014**: System MUST provide model performance metrics (accuracy, precision, recall, expected value) through backtesting on historical data
- **FR-015**: System MUST make match-level picks accessible via API endpoints, either through existing endpoints with filtering or new dedicated endpoints
- **FR-016**: System MUST avoid creating duplicate picks for the same match and prediction type when the pipeline runs multiple times
- **FR-017**: System MUST log all prediction operations, model training events, and errors with sufficient context for debugging

### Key Entities *(include if feature involves data)*

- **Match Prediction Model**: Represents a trained machine learning model for predicting match outcomes (Over/Under 2.5 or BTTS). Key attributes: model type, training date, performance metrics, file location, version.

- **Match-Level Daily Pick**: Represents a daily pick recommendation for a match-level prediction (Over/Under 2.5 or BTTS). Key attributes: match identifier, prediction type, recommendation (Over/Under or Yes/No), model expected probability, bookmaker probability, edge percentage, confidence level, creation timestamp. Relationships: linked to Match entity, distinct from player-level DailyPick.

- **Team Match Features**: Represents aggregated features for a team in a specific match context. Key attributes: team identifier, opponent identifier, home/away status, recent form statistics (goals scored/conceded in last N matches), offensive statistics (shots, shots on target averages), defensive statistics, head-to-head history, bookmaker odds.

- **Historical Match Data**: Represents completed match records used for training. Key attributes: match date, home team, away team, final score, total goals, both teams scored indicator, team statistics (shots, shots on target, corners, etc.), bookmaker odds at match time.

## Feature Engineering Research Priorities

### Over/Under 2.5 Goals Prediction Features

Based on football analytics research and match prediction best practices, the following features are expected to have high predictive value and MUST be researched and tested:

**Team Offensive Capability**:
- Average goals scored per match (season, last 5/10 matches, home/away splits)
- Average shots per match and shots on target per match
- Expected goals (xG) if available from API
- Goals scored trend (improving/declining form)
- Offensive strength rating (goals scored vs. league average)

**Team Defensive Capability**:
- Average goals conceded per match (season, last 5/10 matches, home/away splits)
- Average shots conceded and shots on target conceded
- Expected goals against (xGA) if available
- Goals conceded trend (improving/declining form)
- Defensive strength rating (goals conceded vs. league average)

**Match Context**:
- Home/away performance differential (home team advantage)
- Head-to-head total goals history (last 5 meetings)
- Recent form (goals scored/conceded in last 5 matches)
- Fixture difficulty (opponent strength)
- Days since last match (rest/fatigue factor)
- Bookmaker over/under 2.5 odds and implied probability

**Interaction Features**:
- Combined offensive strength (home team goals scored avg + away team goals scored avg)
- Combined defensive weakness (home team goals conceded avg + away team goals conceded avg)
- Offensive vs. defensive matchup (home goals scored avg vs. away goals conceded avg, and vice versa)

### Both Teams To Score (BTTS) Prediction Features

For BTTS predictions, the following features are expected to be most predictive:

**Team Scoring Consistency**:
- Percentage of matches where team scored (season, last 5/10 matches, home/away splits)
- Average goals scored per match (higher = more likely to score)
- Matches with 0 goals (frequency of scoreless games)
- Scoring streak/trend (consecutive matches with/without goals)

**Team Conceding Consistency**:
- Percentage of matches where team conceded (season, last 5/10 matches, home/away splits)
- Average goals conceded per match
- Clean sheet frequency (matches with 0 goals conceded)
- Conceding streak/trend

**Match Context**:
- Head-to-head BTTS history (both teams scored in last 5 meetings)
- Home team scoring rate vs. away team conceding rate
- Away team scoring rate vs. home team conceding rate
- Bookmaker BTTS odds and implied probability
- Recent form (both teams scored in last 5 matches for each team)

**Interaction Features**:
- Combined scoring probability (home team scoring rate × away team scoring rate)
- Defensive weakness indicator (home conceding rate × away conceding rate)
- Offensive strength vs. defensive weakness matchups

### Feature Engineering Process Requirements

- **FR-FE-001**: System MUST perform exploratory data analysis (EDA) to identify feature distributions, correlations, and relationships with target variables
- **FR-FE-002**: System MUST use feature importance analysis (e.g., LightGBM feature importance, permutation importance, SHAP values) to rank features by predictive power
- **FR-FE-003**: System MUST test multiple feature sets through iterative model training and compare performance metrics (accuracy, precision, recall, expected value)
- **FR-FE-004**: System MUST aggregate player-level statistics to team-level features (sums, averages, medians) for offensive and defensive metrics
- **FR-FE-005**: System MUST create rolling window features (last 5, 10 matches) with proper time-based splitting to avoid data leakage
- **FR-FE-006**: System MUST engineer interaction features that capture team matchup dynamics (offensive strength vs. defensive weakness)
- **FR-FE-007**: System MUST handle missing features gracefully with appropriate imputation strategies (mean, median, forward fill) or exclusion
- **FR-FE-008**: System MUST document final feature sets used in production models with rationale for inclusion/exclusion

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Over/Under 2.5 goals model achieves at least 55% prediction accuracy when backtested on historical Bundesliga matches from the last 2 seasons (2023-2024, 2024-2025)

- **SC-002**: Both Teams To Score model achieves at least 60% prediction accuracy when backtested on historical Bundesliga matches from the last 2 seasons

- **SC-003**: Models generate predictions for at least 90% of upcoming Bundesliga matches within 48 hours when team statistics and bookmaker odds are available

- **SC-004**: Daily pipeline completes match prediction generation and pick storage within 5 minutes for a typical day with 5-10 upcoming matches

- **SC-005**: Match-level picks with 8%+ edge demonstrate positive expected value when evaluated over a 30-day period using historical odds and outcomes

- **SC-006**: System successfully integrates match predictions into daily pipeline without disrupting existing player prop prediction functionality

- **SC-007**: API endpoints return match-level picks alongside player-level picks, with response time under 2 seconds for typical queries

- **SC-008**: Model training process completes successfully using available historical data (5 years of Bundesliga matches) and produces model files ready for production use

- **SC-009**: Feature importance analysis identifies top 10 most predictive features for each model type (Over/Under 2.5 and BTTS), with top 5 features accounting for at least 60% of total feature importance
