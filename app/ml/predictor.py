import pandas as pd
from typing import Dict, Any
import structlog
from app.ml.models.ensemble import EnsembleModel

logger = structlog.get_logger()

def predict_props(features: pd.DataFrame, prop_type: str) -> Dict[str, Any]:
    model = EnsembleModel(prop_type)
    expected_value = model.predict_expected_value(features)
    
    return {
        "expected_value": expected_value,
        "model_obj": model # Return model object to calculate probabilities later with specific lines
    }

def predict_match_outcome(features: pd.DataFrame, prediction_type: str) -> Dict[str, Any]:
    """
    Predict match outcome (Over/Under 2.5 or BTTS) using ensemble models.
    """
    model = EnsembleModel(prediction_type)
    
    # For match predictions, we need probability directly (not expected value)
    # Load models and get probability predictions
    lgb_model = model.lgb_model
    poisson_model = model.poisson_model
    
    predictions = {}
    weights = {}
    
    # LightGBM prediction (binary classification probability)
    if lgb_model:
        try:
            lgb_prob = lgb_model.predict(features)[0]
            predictions['lightgbm'] = float(lgb_prob)
            weights['lightgbm'] = 0.6  # Higher weight for binary classification
        except Exception as e:
            logger.warning(f"LightGBM prediction failed: {e}")
    
    # Poisson prediction (convert expected goals to Over/Under probability)
    if prediction_type == 'over_under_2.5':
        if poisson_model:
            try:
                if isinstance(poisson_model, dict):
                    poisson_m = poisson_model.get('model')
                    scaler = poisson_model.get('scaler')
                    if poisson_m and scaler:
                        features_scaled = scaler.transform(features)
                        expected_goals = poisson_m.predict(features_scaled)[0]
                    else:
                        expected_goals = poisson_m.predict(features)[0]
                else:
                    expected_goals = poisson_model.predict(features)[0]
                
                # Convert to Over/Under probability
                from scipy.stats import poisson as poisson_dist
                pois_prob = 1 - poisson_dist.cdf(2, max(0, expected_goals))
                predictions['poisson'] = float(pois_prob)
                weights['poisson'] = 0.4
            except Exception as e:
                logger.warning(f"Poisson prediction failed: {e}")
                
    elif prediction_type == 'btts':
        # BTTS Poisson Logic
        if model.poisson_home and model.poisson_away:
            try:
                # Predict Home Goals
                ph_model = model.poisson_home.get('model')
                ph_scaler = model.poisson_home.get('scaler')
                if ph_scaler:
                    feat_scaled = ph_scaler.transform(features)
                    exp_home = ph_model.predict(feat_scaled)[0]
                else:
                    exp_home = ph_model.predict(features)[0]
                
                # Predict Away Goals
                pa_model = model.poisson_away.get('model')
                pa_scaler = model.poisson_away.get('scaler')
                if pa_scaler:
                    feat_scaled = pa_scaler.transform(features)
                    exp_away = pa_model.predict(feat_scaled)[0]
                else:
                    exp_away = pa_model.predict(features)[0]
                
                # Calculate P(BTTS) = P(Home > 0) * P(Away > 0)
                from scipy.stats import poisson as poisson_dist
                prob_home_score = 1 - poisson_dist.pmf(0, max(0, exp_home))
                prob_away_score = 1 - poisson_dist.pmf(0, max(0, exp_away))
                
                pois_prob = prob_home_score * prob_away_score
                predictions['poisson'] = float(pois_prob)
                weights['poisson'] = 0.4
                
                # Adjust weights since LightGBM might be weak for BTTS
                weights['lightgbm'] = 0.5
                weights['poisson'] = 0.5
                
            except Exception as e:
                logger.warning(f"Poisson BTTS prediction failed: {e}")
    
    # Ensemble (weighted average)
    total_weight = sum(weights.values())
    if total_weight > 0:
        model_prob = sum(predictions[k] * weights[k] for k in predictions) / total_weight
    else:
        model_prob = 0.5
    
    # Determine recommendation
    if prediction_type == 'over_under_2.5':
        recommendation = 'Over' if model_prob > 0.5 else 'Under'
    else:  # btts
        recommendation = 'Yes' if model_prob > 0.5 else 'No'
    
    # Calculate expected value (for display/logging)
    expected_value = 0.0
    
    if prediction_type == 'over_under_2.5':
        # For O/U, expected value is total goals
        if poisson_model:
            try:
                if isinstance(poisson_model, dict):
                    poisson_m = poisson_model.get('model')
                    scaler = poisson_model.get('scaler')
                    if poisson_m and scaler:
                        features_scaled = scaler.transform(features)
                        expected_value = float(poisson_m.predict(features_scaled)[0])
                    else:
                        expected_value = float(poisson_m.predict(features)[0])
                else:
                    expected_value = float(poisson_model.predict(features)[0])
            except Exception:
                pass
                
    elif prediction_type == 'btts':
        # For BTTS, expected value could be sum of expected home + away goals
        if model.poisson_home and model.poisson_away:
            try:
                # Home Goals
                ph_model = model.poisson_home.get('model')
                ph_scaler = model.poisson_home.get('scaler')
                if ph_scaler:
                    feat_scaled = ph_scaler.transform(features)
                    exp_home = float(ph_model.predict(feat_scaled)[0])
                else:
                    exp_home = float(ph_model.predict(features)[0])
                
                # Away Goals
                pa_model = model.poisson_away.get('model')
                pa_scaler = model.poisson_away.get('scaler')
                if pa_scaler:
                    feat_scaled = pa_scaler.transform(features)
                    exp_away = float(pa_model.predict(feat_scaled)[0])
                else:
                    exp_away = float(pa_model.predict(features)[0])
                    
                expected_value = exp_home + exp_away
            except Exception:
                pass

    return {
        'model_prob': float(model_prob),
        'recommendation': recommendation,
        'predictions': predictions,
        'model_obj': model,
        'expected_value': expected_value
    }
