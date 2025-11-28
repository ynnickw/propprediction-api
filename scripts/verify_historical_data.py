import asyncio
import sys
import os
import pandas as pd

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.ml.match_features import load_match_level_data

def verify_data():
    print("Loading match level data...")
    df = load_match_level_data()
    print(f"Loaded {len(df)} matches")
    
    team = "Borussia Mönchengladbach"
    print(f"\nChecking for team: {team}")
    
    home_matches = df[df['home_team'] == team]
    away_matches = df[df['away_team'] == team]
    
    print(f"Home matches: {len(home_matches)}")
    print(f"Away matches: {len(away_matches)}")
    
    completed_home = home_matches[home_matches['home_score'].notna()]
    print(f"\nCompleted home matches: {len(completed_home)}")
    
    if len(completed_home) > 0:
        print("\nRecent completed home matches:")
        print(completed_home.sort_values('date', ascending=False).head(5)[['date', 'home_team', 'away_team', 'home_score', 'away_score']])
    else:
        print("NO COMPLETED HOME MATCHES FOUND!")

    completed_away = away_matches[away_matches['home_score'].notna()]
    print(f"Completed away matches: {len(completed_away)}")

    if len(completed_away) > 0:
        print("\nRecent completed away matches:")
        print(completed_away.sort_values('date', ascending=False).head(5)[['date', 'home_team', 'away_team', 'home_score', 'away_score']])
    else:
        print("NO COMPLETED AWAY MATCHES FOUND!")

if __name__ == "__main__":
    verify_data()
