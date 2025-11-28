#!/usr/bin/env python3
"""
Quickstart validation script for match-level goals prediction models.

This script validates the success criteria from quickstart.md
"""
import os
import sys
import asyncio
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.ml.match_features import load_match_level_data, engineer_over_under_2_5_features, engineer_btts_features
from app.ml.train_match import prepare_training_data_for_over_under_2_5, prepare_training_data_for_btts
import structlog

logger = structlog.get_logger()


def validate_data_availability():
    """Validate that database connection works and data exists."""
    logger.info("Validating data availability...")
    
    try:
        from app.ml.match_features import load_match_level_data
        df = load_match_level_data()
        
        if len(df) == 0:
            logger.warning("Database connection successful but no matches found")
            return False
            
        logger.info(f"✓ Successfully loaded {len(df)} matches from database")
        return True
        
    except Exception as e:
        logger.error(f"Failed to connect to database or load data: {e}")
        return False


def validate_feature_engineering():
    """Validate feature engineering produces correct features."""
    logger.info("Validating feature engineering...")
    
    try:
        # Load and engineer features
        match_df = load_match_level_data()
        
        # Over/Under 2.5 features
        df_over = engineer_over_under_2_5_features(match_df)
        
        # Check required features exist
        required_features_over = [
            'home_goals_avg_season',
            'away_goals_avg_season',
            'home_goals_conceded_avg_season',
            'away_goals_conceded_avg_season',
            'combined_offensive_strength',
            'h2h_total_goals_avg'
        ]
        
        missing_features = [f for f in required_features_over if f not in df_over.columns]
        if missing_features:
            logger.error(f"Missing Over/Under 2.5 features: {missing_features}")
            return False
        
        logger.info(f"✓ Over/Under 2.5 features: {len([c for c in df_over.columns if c not in ['Date', 'HomeTeam', 'AwayTeam', 'FTHG', 'FTAG']])} features created")
        
        # BTTS features
        df_btts = engineer_btts_features(match_df)
        
        required_features_btts = [
            'home_scoring_rate_season',
            'away_scoring_rate_season',
            'home_conceding_rate_season',
            'away_conceding_rate_season',
            'h2h_btts_rate'
        ]
        
        missing_features = [f for f in required_features_btts if f not in df_btts.columns]
        if missing_features:
            logger.error(f"Missing BTTS features: {missing_features}")
            return False
        
        logger.info(f"✓ BTTS features: {len([c for c in df_btts.columns if c not in ['Date', 'HomeTeam', 'AwayTeam', 'FTHG', 'FTAG']])} features created")
        
        return True
        
    except Exception as e:
        logger.error(f"Feature engineering validation failed: {e}")
        return False


def validate_training_data_preparation():
    """Validate training data preparation."""
    logger.info("Validating training data preparation...")
    
    try:
        # Over/Under 2.5
        df_over, features_over = prepare_training_data_for_over_under_2_5()
        
        if len(df_over) == 0:
            logger.error("No training data for Over/Under 2.5")
            return False
        
        if len(features_over) == 0:
            logger.error("No features extracted for Over/Under 2.5")
            return False
        
        if 'over_2_5' not in df_over.columns:
            logger.error("Target variable 'over_2_5' not found")
            return False
        
        logger.info(f"✓ Over/Under 2.5: {len(df_over)} samples, {len(features_over)} features")
        
        # BTTS
        df_btts, features_btts = prepare_training_data_for_btts()
        
        if len(df_btts) == 0:
            logger.error("No training data for BTTS")
            return False
        
        if len(features_btts) == 0:
            logger.error("No features extracted for BTTS")
            return False
        
        if 'btts' not in df_btts.columns:
            logger.error("Target variable 'btts' not found")
            return False
        
        logger.info(f"✓ BTTS: {len(df_btts)} samples, {len(features_btts)} features")
        
        return True
        
    except Exception as e:
        logger.error(f"Training data preparation validation failed: {e}")
        return False


def validate_model_files():
    """Validate that model files exist (if training has been run)."""
    logger.info("Validating model files...")
    
    model_dir = Path("models")
    model_files = [
        "lgbm_over_under_2.5.txt",
        "poisson_over_under_2.5.joblib",
        "lgbm_btts.txt"
    ]
    
    existing_files = []
    missing_files = []
    
    for file in model_files:
        if (model_dir / file).exists():
            size = (model_dir / file).stat().st_size
            if size > 0:
                existing_files.append(file)
                logger.info(f"✓ {file} exists ({size} bytes)")
            else:
                missing_files.append(file)
                logger.warning(f"✗ {file} exists but is empty")
        else:
            missing_files.append(file)
            logger.warning(f"✗ {file} not found")
    
    if missing_files:
        logger.warning(f"Model files not found (training may not have been run): {missing_files}")
        logger.info("This is expected if models haven't been trained yet")
        return True  # Not a failure, just informational
    
    return True


def validate_database_schema():
    """Validate database schema extensions."""
    logger.info("Validating database schema...")
    
    try:
        from app.core.models import Match, DailyPick
        
        # Check Match model has new fields
        match_fields = ['odds_over_2_5', 'odds_under_2_5', 'odds_btts_yes', 'odds_btts_no']
        for field in match_fields:
            if not hasattr(Match, field):
                logger.error(f"Match model missing field: {field}")
                return False
        
        logger.info("✓ Match model has required fields")
        
        # Check DailyPick model has new fields
        if not hasattr(DailyPick, 'prediction_type'):
            logger.error("DailyPick model missing field: prediction_type")
            return False
        
        # Check player_id is nullable
        # This is harder to check at model level, but we can verify the migration exists
        logger.info("✓ DailyPick model has prediction_type field")
        
        return True
        
    except Exception as e:
        logger.error(f"Database schema validation failed: {e}")
        return False


def validate_api_endpoints():
    """Validate API endpoint structure."""
    logger.info("Validating API endpoints...")
  
    try:
        from app.api.main import app
        from app.core.schemas import PickResponse
        
        # Check PickResponse schema
        if 'prediction_type' not in PickResponse.model_fields:
            logger.error("PickResponse schema missing prediction_type field")
            return False
        
        if 'player_id' not in PickResponse.model_fields:
            logger.error("PickResponse schema missing player_id field")
            return False
        
        logger.info("✓ API schemas have required fields")
        
        # Check routes exist (basic check)
        routes = [route.path for route in app.routes]
        if '/picks' not in routes:
            logger.error("API endpoint /picks not found")
            return False
        
        logger.info("✓ API endpoints configured")
        
        return True
        
    except Exception as e:
        logger.error(f"API endpoint validation failed: {e}")
        return False


def main():
    """Run all validation checks."""
    logger.info("=" * 60)
    logger.info("Quickstart Validation - Match-Level Goals Prediction Models")
    logger.info("=" * 60)
    
    validations = [
        ("Data Availability", validate_data_availability),
        ("Feature Engineering", validate_feature_engineering),
        ("Training Data Preparation", validate_training_data_preparation),
        ("Model Files", validate_model_files),
        ("Database Schema", validate_database_schema),
        ("API Endpoints", validate_api_endpoints),
    ]
    
    results = {}
    for name, validation_func in validations:
        logger.info(f"\n--- {name} ---")
        try:
            results[name] = validation_func()
        except Exception as e:
            logger.error(f"Validation '{name}' raised exception: {e}")
            results[name] = False
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("Validation Summary")
    logger.info("=" * 60)
    
    all_passed = True
    for name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        logger.info(f"{status}: {name}")
        if not passed:
            all_passed = False
    
    logger.info("=" * 60)
    
    if all_passed:
        logger.info("✓ All validations passed!")
        return 0
    else:
        logger.error("✗ Some validations failed. See logs above for details.")
        return 1


if __name__ == "__main__":
    sys.exit(main())

