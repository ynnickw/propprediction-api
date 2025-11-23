# FootProp AI Backend

AI-driven sports betting tool for European football player prop predictions.

## Setup

1.  **Clone the repository**
2.  **Environment Variables**: Copy `.env.example` to `.env` and fill in your API keys.
    ```bash
    cp .env.example .env
    ```
3.  **Run with Docker**:
    ```bash
    docker-compose up --build
    ```
    The API will be available at `http://localhost:8000`.
    Swagger UI: `http://localhost:8000/docs`.

## Development

- **Local Setup**:
  ```bash
  python -m venv venv
  source venv/bin/activate
  pip install -r requirements.txt
  ```
- **Run Migrations**:
  ```bash
  alembic upgrade head
  ```
- **Train Models**:
  ```bash
  python -m app.train
  ```
- **Run Scheduler**:
  The scheduler runs automatically with the app, but can be triggered manually via code if needed.

## Testing

```bash
pytest
```
