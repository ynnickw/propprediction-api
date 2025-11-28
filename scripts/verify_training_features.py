import sys
import os
import pandas as pd

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.ml.train_match import prepare_training_data_for_btts, prepare_training_data_for_over_under_2_5

def check_features():
    print("Checking BTTS training features...")
    try:
        _, btts_features = prepare_training_data_for_btts()
        print(f"BTTS Feature Count: {len(btts_features)}")
        print(f"BTTS Features: {btts_features}")
    except Exception as e:
        print(f"Error checking BTTS features: {e}")

    print("\nChecking Over/Under 2.5 training features...")
    try:
        _, ou_features = prepare_training_data_for_over_under_2_5()
        print(f"Over/Under Feature Count: {len(ou_features)}")
        print(f"Over/Under Features: {ou_features}")
    except Exception as e:
        print(f"Error checking Over/Under features: {e}")

if __name__ == "__main__":
    check_features()
