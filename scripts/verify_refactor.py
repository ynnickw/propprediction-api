import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

print("Verifying imports...")

try:
    from app.config import settings, constants
    print("✅ app.config loaded")
    
    from app.domain import models, schemas
    print("✅ app.domain loaded")
    
    from app.infrastructure.db import session
    from app.infrastructure.clients import api_football, odds_api
    from app.infrastructure import logging
    print("✅ app.infrastructure loaded")
    
    from app.features import pipeline, registry, data_loader
    print("✅ app.features loaded")
    
    from app.ml import base, predictor, utils
    from app.ml.models import ensemble
    from app.ml.training import train_match, train_player_props
    print("✅ app.ml loaded")
    
    from app.services import data_service, prediction_service, scheduler
    print("✅ app.services loaded")
    
    print("\n🎉 All modules imported successfully!")
    
except ImportError as e:
    print(f"\n❌ ImportError: {e}")
    sys.exit(1)
except Exception as e:
    print(f"\n❌ Error: {e}")
    sys.exit(1)
