# Tasks: Match-Level Goals Prediction Models

**Input**: Design documents from `/specs/001-match-goals-model/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Tests are included to comply with constitution testing discipline requirements.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `app/`, `tests/` at repository root
- Paths shown below use existing project structure

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [x] T001 Create directory structure for match prediction modules in app/
- [x] T002 [P] Create app/match_features.py module for feature engineering
- [x] T003 [P] Create app/train_match.py module for match model training
- [x] T004 [P] Create app/match_predictions.py module for prediction logic

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T005 Create Alembic migration to extend Match table with odds_over_2_5, odds_under_2_5, odds_btts_yes, odds_btts_no columns in alembic/versions/
- [x] T006 Create Alembic migration to extend DailyPick table: make player_id nullable, add prediction_type column, add constraints in alembic/versions/
- [x] T007 [P] Implement data loading functions for match-level datasets (D1_*.csv) in app/match_features.py
- [x] T008 [P] Implement data loading functions for player-level dataset aggregation in app/match_features.py
- [x] T009 [P] Implement base feature engineering functions (team statistics aggregation, rolling windows) in app/match_features.py
- [x] T010 [P] Extend data_ingestion.py to fetch Over/Under 2.5 and BTTS odds from The Odds API in app/data_ingestion.py
- [x] T011 Update Match model in app/models.py to include new odds fields (odds_over_2_5, odds_under_2_5, odds_btts_yes, odds_btts_no)
- [x] T012 Update DailyPick model in app/models.py to make player_id nullable and add prediction_type field with validation

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Over/Under 2.5 Goals Prediction Model (Priority: P1) 🎯 MVP

**Goal**: Train and deploy machine learning model for Over/Under 2.5 goals prediction with feature engineering, model training, prediction generation, and edge calculation.

**Independent Test**: Can be fully tested by training the model on historical data, generating predictions for upcoming matches, and verifying predictions include expected value calculations and edge percentages. Model can be evaluated independently using historical backtesting.

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T013 [P] [US1] Unit test for feature engineering functions in tests/unit/test_match_features.py
- [x] T014 [P] [US1] Unit test for Over/Under 2.5 model training in tests/unit/test_match_predictions.py
- [x] T015 [P] [US1] Integration test for Over/Under 2.5 prediction generation in tests/integration/test_match_pipeline.py

### Implementation for User Story 1

- [x] T016 [US1] Implement feature engineering for Over/Under 2.5 goals: load and merge match-level and player-level data in app/match_features.py
- [x] T017 [US1] Implement team-level feature aggregation (goals scored/conceded, shots, rolling averages) for Over/Under 2.5 in app/match_features.py
- [x] T018 [US1] Implement head-to-head history features for Over/Under 2.5 in app/match_features.py
- [x] T019 [US1] Implement interaction features (offensive vs. defensive matchups) for Over/Under 2.5 in app/match_features.py
- [x] T020 [US1] Implement target variable creation (binary: total_goals > 2.5) for Over/Under 2.5 training data in app/train_match.py
- [x] T021 [US1] Implement feature importance analysis and feature selection for Over/Under 2.5 model in app/train_match.py
- [x] T022 [US1] Implement LightGBM model training for Over/Under 2.5 goals prediction in app/train_match.py
- [x] T023 [US1] Implement Poisson regression model training for Over/Under 2.5 goals prediction in app/train_match.py
- [x] T024 [US1] Implement ensemble model (LightGBM + Poisson) for Over/Under 2.5 with weighted averaging in app/model.py
- [x] T025 [US1] Implement model saving (lgbm_over_under_2.5.txt, poisson_over_under_2.5.joblib) in app/train_match.py
- [x] T026 [US1] Implement feature preparation for Over/Under 2.5 predictions (team stats, odds, context) in app/match_predictions.py
- [x] T027 [US1] Implement Over/Under 2.5 prediction generation using trained ensemble model in app/match_predictions.py
- [x] T028 [US1] Implement edge calculation (model_prob vs. bookmaker_prob) for Over/Under 2.5 predictions in app/match_predictions.py
- [x] T029 [US1] Implement backtesting function for Over/Under 2.5 model performance evaluation in app/train_match.py
- [x] T030 [US1] Add logging for Over/Under 2.5 model training and prediction operations in app/train_match.py and app/match_predictions.py

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently. Over/Under 2.5 model can be trained, generate predictions, and calculate edges.

---

## Phase 4: User Story 2 - Both Teams To Score (BTTS) Prediction Model (Priority: P2)

**Goal**: Train and deploy machine learning model for Both Teams To Score (BTTS) prediction with feature engineering, model training, prediction generation, and edge calculation.

**Independent Test**: Can be fully tested by training the model on historical data where target is whether both teams scored (binary classification), generating predictions for upcoming matches, and verifying predictions include expected value calculations. Model can be evaluated independently using historical backtesting.

### Tests for User Story 2

- [ ] T031 [P] [US2] Unit test for BTTS feature engineering functions in tests/unit/test_match_features.py
- [ ] T032 [P] [US2] Unit test for BTTS model training in tests/unit/test_match_predictions.py
- [ ] T033 [P] [US2] Integration test for BTTS prediction generation in tests/integration/test_match_pipeline.py

### Implementation for User Story 2

- [x] T034 [US2] Implement feature engineering for BTTS: scoring/conceding rates, clean sheet frequency, BTTS history in app/match_features.py
- [x] T035 [US2] Implement team scoring consistency features (scoring rate, goals per match, scoreless frequency) for BTTS in app/match_features.py
- [x] T036 [US2] Implement team conceding consistency features (conceding rate, clean sheet frequency) for BTTS in app/match_features.py
- [x] T037 [US2] Implement head-to-head BTTS history features in app/match_features.py
- [x] T038 [US2] Implement interaction features (scoring rate vs. conceding rate matchups) for BTTS in app/match_features.py
- [x] T039 [US2] Implement target variable creation (binary: both teams scored) for BTTS training data in app/train_match.py
- [x] T040 [US2] Implement feature importance analysis and feature selection for BTTS model in app/train_match.py
- [x] T041 [US2] Implement LightGBM model training for BTTS prediction in app/train_match.py
- [x] T042 [US2] Implement Poisson regression model training for BTTS prediction in app/train_match.py
- [x] T043 [US2] Implement ensemble model (LightGBM + Poisson) for BTTS with weighted averaging in app/model.py
- [x] T044 [US2] Implement model saving (lgbm_btts.txt, poisson_btts.joblib) in app/train_match.py
- [x] T045 [US2] Implement feature preparation for BTTS predictions (team stats, odds, context) in app/match_predictions.py
- [x] T046 [US2] Implement BTTS prediction generation using trained ensemble model in app/match_predictions.py
- [x] T047 [US2] Implement edge calculation (model_prob vs. bookmaker_prob) for BTTS predictions in app/match_predictions.py
- [x] T048 [US2] Implement backtesting function for BTTS model performance evaluation in app/train_match.py
- [x] T049 [US2] Add logging for BTTS model training and prediction operations in app/train_match.py and app/match_predictions.py

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently. Both Over/Under 2.5 and BTTS models can be trained, generate predictions, and calculate edges.

---

## Phase 5: User Story 3 - Daily Pipeline Integration for Match Predictions (Priority: P3)

**Goal**: Integrate match-level predictions into existing daily pipeline so picks are automatically generated, stored, and accessible via API alongside player-level picks.

**Independent Test**: Can be fully tested by running the daily pipeline job, verifying match predictions are generated for upcoming matches, checking picks are stored in database with correct structure, and confirming picks are accessible via API endpoints.

### Tests for User Story 3

- [ ] T050 [P] [US3] Integration test for match prediction pipeline execution in tests/integration/test_match_pipeline.py
- [ ] T051 [P] [US3] Contract test for /picks endpoint with match predictions in tests/contract/test_match_picks_schema.py
- [ ] T052 [P] [US3] Contract test for /picks/match endpoint in tests/contract/test_match_picks_schema.py
- [ ] T053 [P] [US3] Integration test for API endpoints returning match picks in tests/integration/test_match_api.py

### Implementation for User Story 3

- [ ] T054 [US3] Extend scheduler.py pipeline_job() to fetch upcoming matches for match predictions in app/scheduler.py
- [ ] T055 [US3] Implement match prediction generation step in pipeline: Over/Under 2.5 predictions for all upcoming matches in app/scheduler.py
- [ ] T056 [US3] Implement match prediction generation step in pipeline: BTTS predictions for all upcoming matches in app/scheduler.py
- [ ] T057 [US3] Implement edge filtering (minimum 8% threshold) for match predictions in app/scheduler.py
- [ ] T058 [US3] Implement DailyPick creation for match-level predictions (prediction_type='over_under_2.5' or 'btts', player_id=null) in app/scheduler.py
- [ ] T059 [US3] Implement duplicate prevention logic (check existing picks by match_id, prediction_type, date) in app/scheduler.py
- [ ] T060 [US3] Extend PickResponse schema to support nullable player_name and prediction_type field in app/schemas.py
- [x] T061 [US3] Create MatchPickResponse schema for match-level picks in app/schemas.py (using PickResponse with nullable fields)
- [x] T062 [US3] Extend /picks endpoint in main.py to filter by prediction_type parameter in app/main.py
- [x] T063 [US3] Implement /picks/match endpoint in main.py to return only match-level picks in app/main.py
- [ ] T064 [US3] Add error handling and logging for match prediction pipeline failures in app/scheduler.py
- [ ] T065 [US3] Add validation for match prediction picks (prediction_type, nullable player_id constraints) in app/scheduler.py

**Checkpoint**: All user stories should now be independently functional. Match predictions are integrated into daily pipeline, picks are stored correctly, and API endpoints return match-level picks.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T066 [P] Update API documentation (OpenAPI/Swagger) with new match prediction endpoints in app/main.py
- [x] T067 [P] Add comprehensive error handling for missing team statistics in app/match_features.py
- [x] T068 [P] Add comprehensive error handling for missing bookmaker odds in app/match_predictions.py
- [x] T069 [P] Implement feature importance documentation and logging for both models in app/train_match.py
- [x] T070 [P] Add performance monitoring and metrics logging for prediction pipeline in app/scheduler.py
- [x] T071 [P] Code cleanup and refactoring: extract common feature engineering patterns in app/match_features.py
- [x] T072 [P] Add unit tests for edge cases (missing data, newly promoted teams) in tests/unit/test_match_features.py
- [x] T073 [P] Add integration tests for edge cases (no upcoming matches, duplicate prevention) in tests/integration/test_match_pipeline.py
- [x] T074 Run quickstart.md validation scenarios to verify all success criteria in specs/001-match-goals-model/quickstart.md
- [ ] T075 [P] Update README.md with match prediction model documentation in README.md

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3+)**: All depend on Foundational phase completion
  - User stories can then proceed in parallel (if staffed)
  - Or sequentially in priority order (P1 → P2 → P3)
- **Polish (Final Phase)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P2)**: Can start after Foundational (Phase 2) - Independent from US1, shares feature engineering patterns
- **User Story 3 (P3)**: Can start after Foundational (Phase 2) - Depends on US1 and US2 being complete (needs trained models)

### Within Each User Story

- Tests (if included) MUST be written and FAIL before implementation
- Feature engineering before model training
- Model training before prediction generation
- Prediction generation before edge calculation
- Core implementation before integration
- Story complete before moving to next priority

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel (T002, T003, T004)
- All Foundational tasks marked [P] can run in parallel (T007, T008, T009, T010)
- Once Foundational phase completes, User Stories 1 and 2 can start in parallel (if team capacity allows)
- All tests for a user story marked [P] can run in parallel
- Feature engineering tasks within a story marked [P] can run in parallel
- Different user stories can be worked on in parallel by different team members (US1 and US2)

---

## Parallel Example: User Story 1

```bash
# Launch all tests for User Story 1 together:
Task: T013 [P] [US1] Unit test for feature engineering functions in tests/unit/test_match_features.py
Task: T014 [P] [US1] Unit test for Over/Under 2.5 model training in tests/unit/test_match_predictions.py
Task: T015 [P] [US1] Integration test for Over/Under 2.5 prediction generation in tests/integration/test_match_pipeline.py

# Launch feature engineering tasks for User Story 1 together (after T016):
Task: T017 [US1] Implement team-level feature aggregation in app/match_features.py
Task: T018 [US1] Implement head-to-head history features in app/match_features.py
Task: T019 [US1] Implement interaction features in app/match_features.py
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1 (Over/Under 2.5 Goals Model)
4. **STOP and VALIDATE**: Test User Story 1 independently
5. Deploy/demo if ready

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → Deploy/Demo (MVP!)
3. Add User Story 2 → Test independently → Deploy/Demo
4. Add User Story 3 → Test independently → Deploy/Demo
5. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1 (Over/Under 2.5)
   - Developer B: User Story 2 (BTTS) - can start in parallel with US1
   - Developer C: Polish tasks or prepare for US3
3. Once US1 and US2 complete:
   - Developer A + B + C: User Story 3 (Pipeline Integration)
4. Stories complete and integrate independently

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Verify tests fail before implementing
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Avoid: vague tasks, same file conflicts, cross-story dependencies that break independence
- User Story 3 depends on US1 and US2 models being trained, but US1 and US2 can be developed in parallel

