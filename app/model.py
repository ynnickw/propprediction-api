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
        
        # Weighted Ensemble
        # Assign weights based on prop type and model strengths
        
        # Default weights (equal)
        w_lgb = 0.5
        w_pois = 0.5
        
        # Context-Aware Weights
        if 'shots' in self.prop_type or 'tackles' in self.prop_type or 'passes' in self.prop_type:
            # Frequent events: LightGBM is better at capturing form/variance
            w_lgb = 0.7
            w_pois = 0.3
        elif 'goal' in self.prop_type or 'card' in self.prop_type or 'assist' in self.prop_type:
            # Rare events: Poisson is theoretically superior for low counts
            w_lgb = 0.3
            w_pois = 0.7
            
        final_pred = 0.0
        total_weight = 0.0
        
        if self.lgb_model:
            # LightGBM prediction
            lgb_pred = self.lgb_model.predict(features)[0]
            lgb_pred = max(0, lgb_pred)
            final_pred += lgb_pred * w_lgb
            total_weight += w_lgb
            
        if self.poisson_model:
            # Poisson Regression prediction
            try:
                pois_pred = self.poisson_model.predict(features)[0]
                pois_pred = max(0, pois_pred)
                final_pred += pois_pred * w_pois
                total_weight += w_pois
            except Exception:
                pass
        
        if total_weight > 0:
            return final_pred / total_weight
            
        # Fallback Heuristic if no models are trained
        # Use recent form + simple adjustments
        
        # 1. Base Value from Recent Form
        base_val = 0.0
        if 'shots' in self.prop_type:
            if 'target' in self.prop_type:
                base_val = features.get('shots_on_target_ema_5', features.get('shots_on_target_last_5', 0)).iloc[0]
            else:
                base_val = features.get('shots_ema_5', features.get('shots_last_5', 0)).iloc[0]
        elif 'goal' in self.prop_type:
            base_val = features.get('goals_last_5', 0).iloc[0]
        elif 'assist' in self.prop_type:
            base_val = features.get('assists_last_5', 0).iloc[0]
        
        # 2. Adjustments
        # Home Advantage (+5%)
        if features.get('is_home', 0).iloc[0] == 1:
            base_val *= 1.05
            
        # Opponent Strength (Conceded Shots Ratio)
        # Compare opponent conceded vs league average (approx 12.0)
        opp_conceded = features.get('opp_conceded_shots_avg', 12.0).iloc[0]
        strength_ratio = opp_conceded / 12.0
        base_val *= strength_ratio
        
        return float(max(0, base_val))

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
