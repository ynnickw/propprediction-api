# Setup Guide

## Python Version Compatibility

**Important**: This project requires Python 3.10-3.13. Python 3.14 is not yet fully supported due to compatibility issues with pydantic-core.

### Recommended: Python 3.11

If you're using Python 3.14, you have two options:

1. **Use Python 3.11 (Recommended)**
   ```bash
   # Using pyenv
   pyenv install 3.11.9
   pyenv local 3.11.9
   
   # Or using conda
   conda create -n proprediction python=3.11
   conda activate proprediction
   ```

2. **Use Docker (Recommended for consistency)**
   ```bash
   docker-compose up --build
   ```
   The Dockerfile uses Python 3.11, so all dependencies will work correctly.

## Local Development Setup

1. **Create virtual environment**
   ```bash
   python3.11 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install dependencies**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

3. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

4. **Run database migrations**
   ```bash
   alembic upgrade head
   ```

5. **Train models**
   ```bash
   python -m app.ml.train
   python -m app.ml.train_match --prop-type over_under_2.5
   ```

## Troubleshooting

### pydantic-core build fails
- **Cause**: Python 3.14 compatibility issue
- **Solution**: Use Python 3.11-3.13 or Docker

### Module import errors after restructure
- **Cause**: Old import paths
- **Solution**: All imports have been updated. Use new paths:
  - `from app.ml.match_features import ...`
  - `from app.core.models import ...`
  - `from app.api.main import app`

### FastAPI not found
- **Cause**: Dependencies not installed
- **Solution**: Run `pip install -r requirements.txt`

### SQLAlchemy TypingOnly error with Python 3.14
- **Error**: `Class <class 'sqlalchemy.sql.elements.SQLCoreOperations'> directly inherits TypingOnly but has additional attributes`
- **Cause**: SQLAlchemy 2.0.25 has compatibility issues with Python 3.14's typing system
- **Solution**: Use Python 3.11-3.13. The Dockerfile uses Python 3.11 for compatibility.

