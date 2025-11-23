import lightgbm as lgb
import pandas as pd
import numpy as np
import os
import joblib
from typing import Dict, Any, Tuple
from scipy.stats import poisson

MODEL_DIR = "models"

class EnsembleModel:
    def __init__(self, prop_type: str):
        self.prop_type = prop_type
        self.lgb_model = self._load_lgb()
        self.poisson_model = self._load_poisson()
    
    def _load_lgb(self):
        model_path = os.path.join(MODEL_DIR, f"lgbm_{self.prop_type}.txt")
        if os.path.exists(model_path):
            return lgb.Booster(model_file=model_path)
        return None

    def _load_poisson(self):
        model_path = os.path.join(MODEL_DIR, f"poisson_{self.prop_type}.joblib")
        if os.path.exists(model_path):
            return joblib.load(model_path)
        return None

    def predict_expected_value(self, features: pd.DataFrame) -> float:
        """
        Predict the expected value (lambda) using an ensemble of LightGBM and Poisson Regression.
        """
        preds = []
        
        if self.lgb_model:
            # LightGBM prediction
            lgb_pred = self.lgb_model.predict(features)[0]
            preds.append(max(0, lgb_pred)) # Ensure non-negative
            
        if self.poisson_model:
            # Poisson Regression prediction
            # Note: The pipeline expects the same feature columns as training
            try:
                pois_pred = self.poisson_model.predict(features)[0]
                preds.append(max(0, pois_pred))
            except Exception:
                pass # Fail gracefully if features mismatch during dev
        
        if not preds:
            return 0.0
            
        # Simple average ensemble
        # In a higher-end version, use weighted average based on CV performance
        return np.mean(preds)

    def calculate_probability(self, expected_value: float, line: float, side: str) -> float:
        """
        Calculate the probability of the outcome using Poisson distribution.
        
        Args:
            expected_value: The predicted average count (lambda).
            line: The betting line (e.g., 3.5).
            side: 'Over' or 'Under'.
            
        Returns:
            Probability (0.0 to 1.0).
        """
        # For integer lines (e.g., 3.0), "Over 3.0" usually means > 3 (i.e., >= 4)
        # For half lines (e.g., 3.5), "Over 3.5" means >= 4
        
        # We treat the line as a threshold.
        # P(X > line) = 1 - P(X <= line)
        # P(X < line) = P(X <= line) - P(X = line) ... roughly
        
        # Standard convention:
        # Over X.5 -> P(k >= X+1) = 1 - CDF(floor(X.5))
        # Under X.5 -> P(k <= X) = CDF(floor(X.5))
        
        threshold = int(np.floor(line))
        
        if side.lower() == 'over':
            # Probability of getting MORE than the threshold
            # e.g. Line 3.5, Threshold 3. We want P(X >= 4) = 1 - P(X <= 3)
            prob = 1 - poisson.cdf(threshold, expected_value)
        else:
            # Probability of getting LESS than or EQUAL to the threshold
            # e.g. Line 3.5, Threshold 3. We want P(X <= 3)
            prob = poisson.cdf(threshold, expected_value)
            
        return prob

def predict_props(features: pd.DataFrame, prop_type: str) -> Dict[str, Any]:
    model = EnsembleModel(prop_type)
    expected_value = model.predict_expected_value(features)
    
    return {
        "expected_value": expected_value,
        "model_obj": model # Return model object to calculate probabilities later with specific lines
    }
