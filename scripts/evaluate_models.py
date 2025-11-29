import pandas as pd
import numpy as np
import os
import joblib
import lightgbm as lgb
from sklearn.metrics import mean_squared_error
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.ml.training.train_player_props import load_data, prepare_training_data
from app.config.settings import settings
import warnings
import structlog

# Suppress warnings and logs
warnings.filterwarnings("ignore")
structlog.configure(
    processors=[structlog.processors.JSONRenderer()],
    logger_factory=structlog.PrintLoggerFactory(file=open(os.devnull, "w")),
)

MODEL_DIR = settings.MODEL_DIR

def evaluate_models():
    props = ['shots', 'shots_on_target', 'goals', 'assists']
    
    print(f"{'Prop':<20} | {'RMSE':<10}")
    print("-" * 35)
    
    df = load_data()
    
    for prop in props:
        try:
            # Load models
            lgb_model = lgb.Booster(model_file=os.path.join(MODEL_DIR, f"lgbm_{prop}.txt"))
            poisson_pipeline = joblib.load(os.path.join(MODEL_DIR, f"poisson_{prop}.joblib"))
            
            # Prepare data
            X, y = prepare_training_data(df, prop)
            
            # Predict
            pred_lgb = lgb_model.predict(X)
            pred_pois = poisson_pipeline.predict(X)
            pred_ensemble = (pred_lgb + pred_pois) / 2
            
            # Calculate RMSE
            rmse = np.sqrt(mean_squared_error(y, pred_ensemble))
            print(f"{prop:<20} | {rmse:.4f}")
            
        except Exception as e:
            print(f"{prop:<20} | Error: {e}")

if __name__ == "__main__":
    evaluate_models()
