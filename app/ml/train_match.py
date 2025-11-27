"""
Training script for match-level prediction models.

This module handles:
- Training LightGBM models for Over/Under 2.5 and BTTS
- Training Poisson regression models
- Feature importance analysis
- Model evaluation and backtesting
- Model saving
"""

import lightgbm as lgb
import pandas as pd
import numpy as np
import os
import joblib
from typing import Dict, List, Tuple
from sklearn.model_selection import TimeSeriesSplit
from sklearn.linear_model import PoissonRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
import structlog
from .model import EnsembleModel

logger = structlog.get_logger()

MODEL_DIR = "models"
os.makedirs(MODEL_DIR, exist_ok=True)


def train_over_under_2_5_model(df: pd.DataFrame, features: List[str], 
                               random_seed: int = 42) -> Dict:
    """
    Train ensemble model for Over/Under 2.5 goals prediction.
    
    Args:
        df: Training DataFrame with features and target
        features: List of feature column names
        random_seed: Random seed for reproducibility
    
    Returns:
        Dictionary with trained models and metrics
    """
    logger.info("Training Over/Under 2.5 goals model")
    
    # Prepare data
    X = df[features].fillna(0)
    y = df['over_2_5']
    
    # Time series split
    tscv = TimeSeriesSplit(n_splits=5)
    
    # Train LightGBM
    lgb_params = {
        'objective': 'binary',
        'metric': 'binary_logloss',
        'boosting_type': 'gbdt',
        'num_leaves': 31,
        'learning_rate': 0.05,
        'feature_fraction': 0.9,
        'bagging_fraction': 0.8,
        'bagging_freq': 5,
        'verbose': -1,
        'random_state': random_seed
    }
    
    lgb_scores = []
    lgb_models = []
    
    for train_idx, val_idx in tscv.split(X):
        X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
        y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]
        
        train_data = lgb.Dataset(X_train, label=y_train)
        val_data = lgb.Dataset(X_val, label=y_val, reference=train_data)
        
        model = lgb.train(
            lgb_params,
            train_data,
            valid_sets=[val_data],
            num_boost_round=100,
            callbacks=[lgb.early_stopping(10), lgb.log_evaluation(0)]
        )
        
        y_pred = model.predict(X_val)
        y_pred_binary = (y_pred > 0.5).astype(int)
        acc = accuracy_score(y_val, y_pred_binary)
        lgb_scores.append(acc)
        lgb_models.append(model)
    
    # Use best model or average
    best_model_idx = np.argmax(lgb_scores)
    final_lgb_model = lgb_models[best_model_idx]
    
    # Train Poisson (for binary classification, use logistic regression approach)
    # For Over/Under, we can model total goals as Poisson, then convert to binary
    poisson_scores = []
    poisson_models = []
    
    # Create total goals target for Poisson
    if 'total_goals' in df.columns:
        y_goals = df['total_goals']
        
        for train_idx, val_idx in tscv.split(X):
            X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
            y_train_goals, y_val_goals = y_goals.iloc[train_idx], y_goals.iloc[val_idx]
            
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_val_scaled = scaler.transform(X_val)
            
            poisson_model = PoissonRegressor(alpha=0.1, max_iter=200)
            poisson_model.fit(X_train_scaled, y_train_goals)
            
            # Predict expected goals, then convert to Over/Under probability
            y_pred_goals = poisson_model.predict(X_val_scaled)
            y_pred_over = (y_pred_goals > 2.5).astype(int)
            acc = accuracy_score(y_val, y_pred_over)
            poisson_scores.append(acc)
            poisson_models.append((poisson_model, scaler))
        
        best_poisson_idx = np.argmax(poisson_scores)
        final_poisson_model, final_scaler = poisson_models[best_poisson_idx]
    else:
        final_poisson_model = None
        final_scaler = None
    
    # Save models
    lgb_path = os.path.join(MODEL_DIR, "lgbm_over_under_2.5.txt")
    final_lgb_model.save_model(lgb_path)
    logger.info(f"Saved LightGBM model to {lgb_path}")
    
    if final_poisson_model:
        poisson_path = os.path.join(MODEL_DIR, "poisson_over_under_2.5.joblib")
        joblib.dump({'model': final_poisson_model, 'scaler': final_scaler}, poisson_path)
        logger.info(f"Saved Poisson model to {poisson_path}")
    
    # Feature importance
    importance_df = analyze_feature_importance(final_lgb_model, features)
    
    # Log top features and their importance
    if not importance_df.empty:
        top_10 = importance_df.head(10)
        logger.info("Top 10 features by importance for Over/Under 2.5:")
        for idx, row in top_10.iterrows():
            logger.info(f"  {row['feature']}: {row['importance']:.4f}")
        
        # Calculate cumulative importance
        total_importance = importance_df['importance'].sum()
        top_5_importance = importance_df.head(5)['importance'].sum()
        top_5_percentage = (top_5_importance / total_importance * 100) if total_importance > 0 else 0
        logger.info(f"Top 5 features account for {top_5_percentage:.1f}% of total importance")
    
    metrics = {
        'lgb_accuracy_mean': np.mean(lgb_scores),
        'lgb_accuracy_std': np.std(lgb_scores),
        'poisson_accuracy_mean': np.mean(poisson_scores) if poisson_scores else 0,
        'poisson_accuracy_std': np.std(poisson_scores) if poisson_scores else 0,
        'feature_importance': importance_df
    }
    
    logger.info(f"LightGBM accuracy: {metrics['lgb_accuracy_mean']:.3f} ± {metrics['lgb_accuracy_std']:.3f}")
    if poisson_scores:
        logger.info(f"Poisson accuracy: {metrics['poisson_accuracy_mean']:.3f} ± {metrics['poisson_accuracy_std']:.3f}")
    
    return {
        'lgb_model': final_lgb_model,
        'poisson_model': final_poisson_model,
        'scaler': final_scaler,
        'metrics': metrics
    }


def train_btts_model(df: pd.DataFrame, features: List[str], 
                     random_seed: int = 42) -> Dict:
    """
    Train ensemble model for Both Teams To Score prediction.
    
    Args:
        df: Training DataFrame with features and target
        features: List of feature column names
        random_seed: Random seed for reproducibility
    
    Returns:
        Dictionary with trained models and metrics
    """
    logger.info("Training BTTS model")
    
    # Prepare data
    X = df[features].fillna(0)
    y = df['btts']
    
    # Time series split
    tscv = TimeSeriesSplit(n_splits=5)
    
    # Train LightGBM (binary classification)
    lgb_params = {
        'objective': 'binary',
        'metric': 'binary_logloss',
        'boosting_type': 'gbdt',
        'num_leaves': 31,
        'learning_rate': 0.05,
        'feature_fraction': 0.9,
        'bagging_fraction': 0.8,
        'bagging_freq': 5,
        'verbose': -1,
        'random_state': random_seed
    }
    
    lgb_scores = []
    lgb_models = []
    
    for train_idx, val_idx in tscv.split(X):
        X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
        y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]
        
        train_data = lgb.Dataset(X_train, label=y_train)
        val_data = lgb.Dataset(X_val, label=y_val, reference=train_data)
        
        model = lgb.train(
            lgb_params,
            train_data,
            valid_sets=[val_data],
            num_boost_round=100,
            callbacks=[lgb.early_stopping(10), lgb.log_evaluation(0)]
        )
        
        y_pred = model.predict(X_val)
        y_pred_binary = (y_pred > 0.5).astype(int)
        acc = accuracy_score(y_val, y_pred_binary)
        lgb_scores.append(acc)
        lgb_models.append(model)
    
    # Use best model
    best_model_idx = np.argmax(lgb_scores)
    final_lgb_model = lgb_models[best_model_idx]
    
    # For BTTS, Poisson is less relevant (it's binary, not count data)
    # But we can still use it by modeling expected goals for each team
    # For simplicity, we'll skip Poisson for BTTS and use LightGBM only
    final_poisson_model = None
    final_scaler = None
    
    # Save models
    lgb_path = os.path.join(MODEL_DIR, "lgbm_btts.txt")
    final_lgb_model.save_model(lgb_path)
    logger.info(f"Saved LightGBM BTTS model to {lgb_path}")
    
    # Feature importance
    importance_df = analyze_feature_importance(final_lgb_model, features)
    
    # Log top features and their importance
    if not importance_df.empty:
        top_10 = importance_df.head(10)
        logger.info("Top 10 features by importance for BTTS:")
        for idx, row in top_10.iterrows():
            logger.info(f"  {row['feature']}: {row['importance']:.4f}")
        
        # Calculate cumulative importance
        total_importance = importance_df['importance'].sum()
        top_5_importance = importance_df.head(5)['importance'].sum()
        top_5_percentage = (top_5_importance / total_importance * 100) if total_importance > 0 else 0
        logger.info(f"Top 5 features account for {top_5_percentage:.1f}% of total importance")
    
    metrics = {
        'lgb_accuracy_mean': np.mean(lgb_scores),
        'lgb_accuracy_std': np.std(lgb_scores),
        'feature_importance': importance_df
    }
    
    logger.info(f"BTTS LightGBM accuracy: {metrics['lgb_accuracy_mean']:.3f} ± {metrics['lgb_accuracy_std']:.3f}")
    
    return {
        'lgb_model': final_lgb_model,
        'poisson_model': final_poisson_model,
        'scaler': final_scaler,
        'metrics': metrics
    }


def analyze_feature_importance(model, features: List[str]) -> pd.DataFrame:
    """
    Analyze and rank feature importance.
    
    Args:
        model: Trained LightGBM model
        features: List of feature names
    
    Returns:
        DataFrame with feature importance rankings
    """
    if hasattr(model, 'feature_importances_'):
        importance_df = pd.DataFrame({
            'feature': features,
            'importance': model.feature_importances_
        }).sort_values('importance', ascending=False)
        
        logger.info("Top 10 features by importance:")
        logger.info(importance_df.head(10).to_string())
        
        return importance_df
    
    return pd.DataFrame()


def prepare_training_data_for_btts() -> Tuple[pd.DataFrame, List[str]]:
    """
    Prepare training data for BTTS model.
    
    Returns:
        Tuple of (DataFrame with features, list of feature names)
    """
    from .match_features import load_match_level_data, engineer_btts_features
    
    # Load match data
    match_df = load_match_level_data()
    
    # Engineer features
    df = engineer_btts_features(match_df)
    
    # Select feature columns (exclude target and metadata)
    exclude_cols = ['date', 'Date', 'Div', 'Time', 'HomeTeam', 'AwayTeam', 
                    'FTHG', 'FTAG', 'FTR', 'HTHG', 'HTAG', 'HTR',
                    'total_goals', 'over_2_5', 'btts', 'year']
    
    feature_cols = [col for col in df.columns if col not in exclude_cols and df[col].dtype in [np.float64, np.int64]]
    
    # Remove rows with missing target
    df = df[df['btts'].notna()]
    
    logger.info(f"Prepared {len(df)} samples with {len(feature_cols)} features for BTTS")
    
    return df, feature_cols


def train_btts():
    """Main training function for BTTS model."""
    logger.info("=" * 60)
    logger.info("Training Both Teams To Score (BTTS) Model")
    logger.info("=" * 60)
    
    # Prepare data
    df, features = prepare_training_data_for_btts()
    
    # Train model
    result = train_btts_model(df, features, random_seed=42)
    
    logger.info("BTTS training completed successfully")
    return result


def prepare_training_data_for_over_under_2_5() -> Tuple[pd.DataFrame, List[str]]:
    """
    Prepare training data for Over/Under 2.5 goals model.
    
    Returns:
        Tuple of (DataFrame with features, list of feature names)
    """
    from .match_features import load_match_level_data, engineer_over_under_2_5_features
    
    # Load match data
    match_df = load_match_level_data()
    
    # Engineer features
    df = engineer_over_under_2_5_features(match_df)
    
    # Select feature columns (exclude target and metadata)
    exclude_cols = ['date', 'Date', 'Div', 'Time', 'HomeTeam', 'AwayTeam', 
                    'FTHG', 'FTAG', 'FTR', 'HTHG', 'HTAG', 'HTR',
                    'total_goals', 'over_2_5', 'btts', 'year']
    
    feature_cols = [col for col in df.columns if col not in exclude_cols and df[col].dtype in [np.float64, np.int64]]
    
    # Remove rows with missing target
    df = df[df['over_2_5'].notna()]
    
    logger.info(f"Prepared {len(df)} samples with {len(feature_cols)} features")
    
    return df, feature_cols


def train_over_under_2_5():
    """Main training function for Over/Under 2.5 goals model."""
    logger.info("=" * 60)
    logger.info("Training Over/Under 2.5 Goals Model")
    logger.info("=" * 60)
    
    # Prepare data
    df, features = prepare_training_data_for_over_under_2_5()
    
    # Train model
    result = train_over_under_2_5_model(df, features, random_seed=42)
    
    logger.info("Training completed successfully")
    return result


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == '--prop-type':
        prop_type = sys.argv[2] if len(sys.argv) > 2 else 'over_under_2.5'
        if prop_type == 'over_under_2.5':
            train_over_under_2_5()
        elif prop_type == 'btts':
            train_btts()
        else:
            logger.error(f"Unknown prop type: {prop_type}")
    else:
        # Train both models by default
        train_over_under_2_5()
        train_btts()

