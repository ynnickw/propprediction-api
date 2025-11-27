"""
Machine Learning module for FootProp AI Backend.

Contains model training, feature engineering, and prediction logic.
"""

# Lazy imports to avoid loading heavy dependencies when not needed
def __getattr__(name):
    if name == "EnsembleModel":
        from .model import EnsembleModel
        return EnsembleModel
    elif name == "predict_props":
        from .model import predict_props
        return predict_props
    elif name == "predict_match_outcome":
        from .model import predict_match_outcome
        return predict_match_outcome
    elif name == "prepare_features":
        from .features import prepare_features
        return prepare_features
    elif name == "calculate_rolling_stats":
        from .features import calculate_rolling_stats
        return calculate_rolling_stats
    elif name == "load_match_level_data":
        from .match_features import load_match_level_data
        return load_match_level_data
    elif name == "engineer_over_under_2_5_features":
        from .match_features import engineer_over_under_2_5_features
        return engineer_over_under_2_5_features
    elif name == "engineer_btts_features":
        from .match_features import engineer_btts_features
        return engineer_btts_features
    elif name == "prepare_match_features_for_prediction":
        from .match_features import prepare_match_features_for_prediction
        return prepare_match_features_for_prediction
    elif name == "predict_match":
        from .match_predictions import predict_match_outcome as predict_match
        return predict_match
    elif name == "calculate_edge":
        from .match_predictions import calculate_edge
        return calculate_edge
    elif name == "filter_picks_by_edge":
        from .match_predictions import filter_picks_by_edge
        return filter_picks_by_edge
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

__all__ = [
    "EnsembleModel",
    "predict_props",
    "predict_match_outcome",
    "prepare_features",
    "calculate_rolling_stats",
    "load_match_level_data",
    "engineer_over_under_2_5_features",
    "engineer_btts_features",
    "prepare_match_features_for_prediction",
    "predict_match",
    "calculate_edge",
    "filter_picks_by_edge",
]

