<!--
Sync Impact Report:
Version change: N/A → 1.0.0 (initial version)
Modified principles: N/A (initial creation)
Added sections: Core Principles (5), Technology Stack Requirements, Development Workflow, Governance
Removed sections: N/A
Templates requiring updates:
  ✅ plan-template.md - Constitution Check section exists and will reference these principles
  ✅ spec-template.md - No direct constitution references, compatible
  ✅ tasks-template.md - No direct constitution references, compatible
Follow-up TODOs: None
-->

# FootProp AI Backend Constitution

## Core Principles

### I. API-First Design
All functionality MUST be exposed through well-defined REST API endpoints. Endpoints MUST follow RESTful conventions, use appropriate HTTP methods, and return consistent JSON responses. API contracts MUST be documented via OpenAPI/Swagger. Internal business logic MUST be separated from API layer to enable reuse and testing. Rationale: Ensures the service remains consumable by various clients and maintains clear boundaries between interface and implementation.

### II. Data Quality & Validation (NON-NEGOTIABLE)
All external data ingestion MUST validate schema, types, and business rules before persistence. Missing or invalid data MUST be logged with context and handled gracefully (fail-safe defaults or explicit errors). Data transformations MUST be idempotent where possible. Database constraints MUST enforce referential integrity and data consistency. Rationale: ML model accuracy depends on data quality; invalid data corrupts predictions and business value.

### III. Model Versioning & Reproducibility
All ML models MUST be versioned and stored in the `models/` directory with descriptive filenames. Model training MUST be reproducible: random seeds fixed, dependencies pinned, training scripts version-controlled. Model performance metrics MUST be logged and tracked. Model deployment MUST include rollback capability. Rationale: Enables model comparison, debugging, and safe production updates without breaking existing predictions.

### IV. Observability & Logging
All critical operations (data ingestion, model predictions, API requests) MUST emit structured logs with appropriate levels (INFO, WARNING, ERROR). Logs MUST include request IDs, timestamps, and sufficient context for debugging. Health check endpoints MUST expose service status. Errors MUST include stack traces in development and sanitized messages in production. Rationale: Production ML systems require visibility into data flow, model behavior, and failure modes for rapid diagnosis.

### V. Testing Discipline
Unit tests MUST cover core business logic, data transformations, and model inference paths. Integration tests MUST validate API endpoints, database operations, and scheduled task execution. Contract tests MUST verify API response schemas. Tests MUST be runnable in CI/CD and locally via Docker. Test data MUST be isolated and not depend on external APIs. Rationale: Prevents regressions in data pipelines and model behavior, ensuring predictions remain reliable as code evolves.

## Technology Stack Requirements

**Backend Framework**: FastAPI for async API development and automatic OpenAPI documentation.

**Database**: PostgreSQL via Supabase with Alembic for schema migrations. All schema changes MUST go through migrations; direct database modifications are prohibited.

**Containerization**: Docker and Docker Compose for local development and deployment. Services MUST be containerized and environment-agnostic via environment variables.

**ML Framework**: LightGBM and scikit-learn for model training. Models MUST be serialized in formats compatible with production inference (joblib, native formats).

**Scheduling**: APScheduler or similar for periodic data ingestion tasks. Scheduled tasks MUST be idempotent and handle failures gracefully with retry logic.

**Dependencies**: All Python dependencies MUST be pinned in `requirements.txt` with exact versions. Virtual environments MUST be used for local development.

## Development Workflow

**Branch Strategy**: Feature branches from `main`. All changes MUST be reviewed before merge. `main` branch MUST remain deployable at all times.

**Database Migrations**: Schema changes MUST be created via Alembic migrations. Migrations MUST be tested on a copy of production schema before deployment. Migration rollback scripts MUST be verified.

**Code Review Requirements**: All PRs MUST pass linting and type checking. PRs affecting data ingestion or model training MUST include validation of data quality and model performance. PRs MUST include updated API documentation if endpoints change.

**Deployment Process**: Production deployments MUST be via Docker containers. Environment variables MUST be managed securely (never committed). Database migrations MUST run automatically on deployment with verification steps.

**Testing Gates**: All tests MUST pass before merge. Integration tests MUST run against containerized services. Model training scripts MUST be validated on sample data before full training runs.

## Governance

This constitution supersedes all other development practices and coding standards. All code, architecture decisions, and workflows MUST comply with these principles.

**Amendment Procedure**: Constitution changes require:
1. Documentation of rationale and impact analysis
2. Review and approval (via PR with constitution update)
3. Update to dependent templates and documentation
4. Version bump following semantic versioning (MAJOR.MINOR.PATCH)
5. Communication to team members

**Compliance Review**: All PRs and architecture reviews MUST verify adherence to constitution principles. Violations MUST be justified in Complexity Tracking sections of implementation plans, or the code MUST be refactored to comply.

**Versioning Policy**: Constitution versions follow semantic versioning:
- **MAJOR**: Backward-incompatible principle removals or fundamental redefinitions
- **MINOR**: New principles added or existing principles materially expanded
- **PATCH**: Clarifications, wording improvements, typo fixes, non-semantic refinements

**Version**: 1.0.0 | **Ratified**: 2025-11-27 | **Last Amended**: 2025-11-27
