# FootProp AI Backend

AI-driven sports betting tool for European football player prop predictions using machine learning.

## Quick Start

### Prerequisites

- Docker & Docker Compose
- API Keys: [API-Football](https://www.api-football.com/) and [The Odds API](https://the-odds-api.com/)

### Setup

1. **Clone and configure**

   ```bash
   git clone <repo-url>
   cd proprediction
   cp .env.example .env
   ```

2. **Add API keys to `.env`**

   ```
   API_FOOTBALL_KEY=your_key_here
   THE_ODDS_API_KEY=your_key_here
   SECRET_KEY=generate_random_string
   ```

3. **Start services**

   ```bash
   supabase start
   docker-compose up --build
   ```

4. **Run migrations**

   ```bash
   docker-compose run --rm backend alembic upgrade head
   ```

5. **Train models**

   ```bash
   docker-compose run --rm backend python -m app.train
   ```

6. **Access API**
   - API: `http://localhost:8000`
   - Docs: `http://localhost:8000/docs`
   - Supabase Studio: `http://localhost:54323`

## How It Works

1. **Data Ingestion**: Fetches upcoming matches and player prop odds from APIs every 6 hours
2. **Feature Engineering**: Calculates rolling averages and player statistics
3. **Prediction**: Ensemble model (LightGBM + Poisson) predicts expected values
4. **Edge Calculation**: Compares model probability vs bookmaker odds to find value bets
5. **Picks**: Generates daily picks with 8%+ edge, accessible via `/picks` endpoint

## Development

**Manual pipeline run:**

```bash
docker-compose run --rm backend python run_pipeline.py
```

**Check data:**

```bash
docker-compose run --rm backend python check_data.py
```

**Stop services:**

```bash
docker-compose down
supabase stop
```
