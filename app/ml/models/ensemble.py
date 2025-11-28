import lightgbm as lgb
import joblib
import os
import pandas as pd
from typing import Tuple, Optional, Any, Dict
import structlog
from app.ml.base import BaseModel

logger = structlog.get_logger()

# TODO: Move to settings
from app.config.settings import settings

MODEL_DIR = settings.MODEL_DIR

class EnsembleModel(BaseModel):
    def __init__(self, prop_type: str):
        self.prop_type = prop_type
        self.lgb_model = self._load_lgb()
        
        if prop_type == 'btts':
            self.poisson_home, self.poisson_away = self._load_poisson_btts()
            self.poisson_model = None
        else:
            self.poisson_model = self._load_poisson()
            self.poisson_home = None
            self.poisson_away = None
    
    def _load_lgb(self) -> Optional[lgb.Booster]:
        model_path = os.path.join(MODEL_DIR, f"lgbm_{self.prop_type}.txt")
        if os.path.exists(model_path):
            return lgb.Booster(model_file=model_path)
        return None

    def _load_poisson(self) -> Optional[Any]:
        model_path = os.path.join(MODEL_DIR, f"poisson_{self.prop_type}.joblib")
        if os.path.exists(model_path):
            loaded = joblib.load(model_path)
            if isinstance(loaded, dict):
                return loaded
            return loaded
        return None

    def _load_poisson_btts(self) -> Tuple[Optional[Any], Optional[Any]]:
        home_path = os.path.join(MODEL_DIR, "poisson_home_goals.joblib")
        away_path = os.path.join(MODEL_DIR, "poisson_away_goals.joblib")
        home_model = joblib.load(home_path) if os.path.exists(home_path) else None
        away_model = joblib.load(away_path) if os.path.exists(away_path) else None
        return home_model, away_model

    def predict(self, features: pd.DataFrame) -> float:
        """
        Generic predict method. For specialized predictions (expected value, probability),
        use specific methods.
        """
        return self.predict_expected_value(features)

    def predict_expected_value(self, features: pd.DataFrame) -> float:
        """
        Predict the expected value (lambda) using an ensemble of LightGBM and Poisson Regression.
        """
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
                if isinstance(self.poisson_model, dict):
                    # Model with scaler
                    poisson_m = self.poisson_model.get('model')
                    scaler = self.poisson_model.get('scaler')
                    if poisson_m and scaler:
                        # Note: features should be compatible with scaler
                        features_scaled = scaler.transform(features)
                        pois_pred = poisson_m.predict(features_scaled)[0]
                    else:
                        pois_pred = poisson_m.predict(features)[0]
                else:
                    pois_pred = self.poisson_model.predict(features)[0]
                pois_pred = max(0, pois_pred)
                final_pred += pois_pred * w_pois
                total_weight += w_pois
            except Exception as e:
                logger.warning(f"Poisson prediction failed: {e}")
                pass
        
        if total_weight > 0:
            return final_pred / total_weight
            
        # Fallback Heuristic if no models are trained
        return self._fallback_heuristic(features)

    def _fallback_heuristic(self, features: pd.DataFrame) -> float:
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
        opp_conceded = features.get('opp_conceded_shots_avg', 12.0).iloc[0]
        strength_ratio = opp_conceded / 12.0
        base_val *= strength_ratio
        
        return float(max(0, base_val))

    def load(self, path: str) -> None:
        pass

    def calculate_probability(self, expected_value: float, line: float, side: str = 'Over') -> float:
        """
        Calculate the probability of the outcome using Poisson distribution.
        
        Args:
            expected_value: The predicted expected value (lambda)
            line: The betting line (e.g., 2.5)
            side: 'Over' or 'Under'
            
        Returns:
            Probability of the outcome
        """
        from scipy.stats import poisson
        
        if side == 'Over':
            # P(X > line) = 1 - P(X <= line)
            # Since line is usually x.5, we use floor(line)
            # e.g., P(X > 2.5) = 1 - P(X <= 2)
            prob = 1 - poisson.cdf(int(line), expected_value)
        else:
            # P(X < line) = P(X <= line)
            # e.g., P(X < 2.5) = P(X <= 2)
            prob = poisson.cdf(int(line), expected_value)
            
        return prob
