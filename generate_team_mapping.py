import pandas as pd
import os
import difflib
import structlog

logger = structlog.get_logger()

DATA_DIR = "data"

def get_all_api_teams():
    """Get all unique team names from local player stats files."""
    all_files = [f for f in os.listdir(DATA_DIR) if f.startswith("player_stats_Bundesliga_") and f.endswith(".csv")]
    teams = set()
    for f in all_files:
        try:
            df = pd.read_csv(os.path.join(DATA_DIR, f))
            if 'team' in df.columns:
                teams.update(df['team'].unique())
            if 'opponent' in df.columns:
                teams.update(df['opponent'].unique())
        except Exception:
            pass
    return sorted(list(teams))

def get_all_external_teams():
    """Get all unique team names from external match data files."""
    all_files = [f for f in os.listdir(DATA_DIR) if f.startswith("D1_") and f.endswith(".csv")]
    teams = set()
    for f in all_files:
        try:
            df = pd.read_csv(os.path.join(DATA_DIR, f))
            if 'HomeTeam' in df.columns:
                teams.update(df['HomeTeam'].dropna().unique())
            if 'AwayTeam' in df.columns:
                teams.update(df['AwayTeam'].dropna().unique())
        except Exception:
            pass
    return sorted(list(teams))

def main():
    print("Gathering team names...")
    api_teams = get_all_api_teams()
    ext_teams = get_all_external_teams()
    
    print(f"Found {len(api_teams)} teams in API data.")
    print(f"Found {len(ext_teams)} teams in External data.")
    
    mapping = {}
    unmapped = []
    
    print("\nGenerating Mapping...")
    print("-" * 60)
    
    for api_team in api_teams:
        # 1. Exact Match
        if api_team in ext_teams:
            mapping[api_team] = api_team
            continue
            
        # 2. Fuzzy Match
        matches = difflib.get_close_matches(api_team, ext_teams, n=1, cutoff=0.4)
        if matches:
            best_match = matches[0]
            mapping[api_team] = best_match
            # Visual check for user
            if api_team != best_match:
                print(f"Mapped: '{api_team}' -> '{best_match}'")
        else:
            unmapped.append(api_team)
            print(f"❌ NO MATCH FOUND: '{api_team}'")

    print("-" * 60)
    print("\nGenerated Dictionary for Python:")
    print("mapping = {")
    for k, v in sorted(mapping.items()):
        print(f"    '{k}': '{v}',")
    print("}")
    
    if unmapped:
        print(f"\nWARNING: {len(unmapped)} teams could not be mapped automatically:")
        for t in unmapped:
            print(f"- {t}")

if __name__ == "__main__":
    main()
