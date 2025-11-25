import pandas as pd
import requests
import os
import structlog
from io import StringIO

logger = structlog.get_logger()

DATA_DIR = "data"
OUTPUT_FILE = os.path.join(DATA_DIR, "player_stats_history_enriched.csv")

# Football-Data.co.uk URLs
EXTERNAL_DATA_URLS = {
    2020: "https://www.football-data.co.uk/mmz4281/2021/D1.csv",
    2021: "https://www.football-data.co.uk/mmz4281/2122/D1.csv",
    2022: "https://www.football-data.co.uk/mmz4281/2223/D1.csv",
    2023: "https://www.football-data.co.uk/mmz4281/2324/D1.csv",
    2024: "https://www.football-data.co.uk/mmz4281/2425/D1.csv",
    2025: "https://www.football-data.co.uk/mmz4281/2526/D1.csv"
}

def load_and_concat_player_data():
    """Concatenate all seasonal player stats files."""
    all_files = [f for f in os.listdir(DATA_DIR) if f.startswith("player_stats_Bundesliga_") and f.endswith(".csv")]
    all_files.sort()
    
    dfs = []
    for f in all_files:
        path = os.path.join(DATA_DIR, f)
        logger.info(f"Loading {path}...")
        try:
            df = pd.read_csv(path)
            dfs.append(df)
        except Exception as e:
            logger.error(f"Failed to load {path}: {e}")
            
    if not dfs:
        raise ValueError("No player stats files found!")
        
    combined = pd.concat(dfs, ignore_index=True)
    combined['date'] = pd.to_datetime(combined['date'])
    logger.info(f"Combined player data: {len(combined)} rows")
    return combined

def download_external_data():
    """Download and combine Football-Data.co.uk match data."""
    external_dfs = []
    
    for season, url in EXTERNAL_DATA_URLS.items():
        logger.info(f"Downloading external data for {season} from {url}...")
        try:
            resp = requests.get(url)
            resp.raise_for_status()
            # Handle potential encoding issues
            content = resp.content.decode('utf-8', errors='replace')
            
            # Save individual file
            filename = f"D1_{season}.csv"
            filepath = os.path.join(DATA_DIR, filename)
            with open(filepath, "w") as f:
                f.write(content)
            logger.info(f"Saved {filename}")
            
            df = pd.read_csv(StringIO(content))
            
            # Standardize Date format (usually DD/MM/YYYY in these files)
            df['Date'] = pd.to_datetime(df['Date'], dayfirst=True, errors='coerce')
            
            # Keep relevant columns
            # Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,FTR,HTHG,HTAG,HTR,HS,AS,HST,AST,HF,AF,HC,AC,HY,AY,HR,AR,B365H,B365D,B365A
            # Keep ONLY relevant columns for the model
            # We need:
            # 1. Identifiers: Date, HomeTeam, AwayTeam
            # 2. Match Stats (for historical averages): Shots (HS/AS), Shots on Target (HST/AST), Corners (HC/AC)
            # 3. Odds (for pre-match context): B365H, B365D, B365A (Bet365 is standard)
            # 4. Intensity (optional but good for context): Fouls (HF/AF), Cards (HY/AY/HR/AR)
            cols_to_keep = [
                'Date', 'HomeTeam', 'AwayTeam', 
                'HS', 'AS', 'HST', 'AST',  # Team Shots, Shots on Target
                'HC', 'AC',                # Corners
                'HF', 'AF',                # Fouls
                'HY', 'AY', 'HR', 'AR',    # Cards (Yellow/Red)
                'B365H', 'B365D', 'B365A'  # Odds (Bet365)
            ]
            # Filter columns that exist
            existing_cols = [c for c in cols_to_keep if c in df.columns]
            df = df[existing_cols]
            
            external_dfs.append(df)
            
        except Exception as e:
            logger.error(f"Failed to download/process {url}: {e}")
            
    if not external_dfs:
        return pd.DataFrame()
        
    combined_ext = pd.concat(external_dfs, ignore_index=True)
    logger.info(f"Combined external match data: {len(combined_ext)} rows")
    return combined_ext

def map_team_names(player_df, external_df):
    """
    Map team names between API-Football (player_df) and Football-Data.co.uk (external_df).
    This is a simple fuzzy match or manual mapping.
    """
    # Get unique team names
    api_teams = sorted(player_df['team'].unique())
    ext_teams = sorted(external_df['HomeTeam'].dropna().unique())
    
    # Simple manual mapping for common Bundesliga discrepancies
    # API-Football -> Football-Data.co.uk
    mapping = {
        '1. FC Heidenheim': 'Heidenheim',
        '1.FC Köln': 'FC Koln',
        '1899 Hoffenheim': 'Hoffenheim',
        'Arminia Bielefeld': 'Bielefeld',
        'Bayer Leverkusen': 'Leverkusen',
        'Bayern Munich': 'Bayern Munich',
        'Bayern München': 'Bayern Munich',
        'Borussia Dortmund': 'Dortmund',
        'Borussia Monchengladbach': "M'gladbach",
        'Borussia Mönchengladbach': "M'gladbach",
        'Eintracht Frankfurt': 'Ein Frankfurt',
        'FC Augsburg': 'Augsburg',
        'FC Heidenheim': 'Heidenheim',
        'FC Koln': 'FC Koln',
        'FC Schalke 04': 'Schalke 04',
        'FC St. Pauli': 'St Pauli',
        'FSV Mainz 05': 'Mainz',
        'Hertha Berlin': 'Hertha',
        'Hertha BSC': 'Hertha',
        'Holstein Kiel': 'Holstein Kiel',
        'RB Leipzig': 'RB Leipzig',
        'SC Freiburg': 'Freiburg',
        'SV Darmstadt 98': 'Darmstadt',
        'SpVgg Greuther Furth': 'Greuther Furth',
        'Union Berlin': 'Union Berlin',
        'VfB Stuttgart': 'Stuttgart',
        'VfL BOCHUM': 'Bochum',
        'VfL Bochum': 'Bochum',
        'VfL Wolfsburg': 'Wolfsburg',
        'Vfl Bochum': 'Bochum',
        'Werder Bremen': 'Werder Bremen',
        'Schalke 04': 'Schalke 04'
    }
    
    # Apply mapping to a new column in player_df for merging
    player_df['mapped_team'] = player_df['team'].map(mapping).fillna(player_df['team'])
    player_df['mapped_opponent'] = player_df['opponent'].map(mapping).fillna(player_df['opponent'])
    
    return player_df

def main():
    logger.info("Starting data preparation...")
    
    # 1. Load Player Data
    player_df = load_and_concat_player_data()
    
    # 2. Load External Data
    ext_df = download_external_data()
    
    # Save external data to disk for inspection
    ext_df.to_csv(os.path.join(DATA_DIR, "external_match_data_combined.csv"), index=False)
    
    if ext_df.empty:
        logger.warning("No external data found. Saving player data only.")
        player_df.to_csv(OUTPUT_FILE, index=False)
        return

    # 3. Merge Data
    # We merge on Date and HomeTeam (mapped)
    # First, map team names in player_df
    player_df = map_team_names(player_df, ext_df)
    
    # Check for unmapped teams
    unmapped = player_df[player_df['mapped_team'].isna()]['team'].unique()
    if len(unmapped) > 0:
        logger.warning(f"Unmapped teams in player data: {unmapped}")
        
    # Construct 'MatchHomeTeam' column in player_df
    player_df['MatchHomeTeam'] = player_df.apply(
        lambda x: x['mapped_team'] if x['is_home'] == 1 else x['mapped_opponent'], axis=1
    )
    
    # Debug: Check for unmapped MatchHomeTeams
    missing_home_teams = player_df[player_df['MatchHomeTeam'].isna()]
    if not missing_home_teams.empty:
        logger.warning(f"Found {len(missing_home_teams)} rows with NaN MatchHomeTeam (likely due to missing opponent mapping)")
        logger.warning(f"Sample missing opponents: {missing_home_teams['opponent'].unique()}")

    # Merge
    # Ensure dates match (normalize to midnight and remove timezone)
    player_df['date_norm'] = player_df['date'].dt.normalize().dt.tz_localize(None)
    ext_df['Date'] = pd.to_datetime(ext_df['Date']).dt.normalize()
    
    # Debug: Print sample dates and teams from both to verify format
    logger.info(f"Player Data Sample Date: {player_df['date_norm'].iloc[0]}")
    logger.info(f"External Data Sample Date: {ext_df['Date'].iloc[0]}")
    
    logger.info("Merging player data with external match stats...")
    merged = pd.merge(
        player_df,
        ext_df,
        left_on=['date_norm', 'MatchHomeTeam'],
        right_on=['Date', 'HomeTeam'],
        how='left',
        suffixes=('', '_ext')
    )
    
    # Check merge success
    # Note: HomeTeam comes from ext_df. Since it's not in player_df, it won't have a suffix.
    matched_count = merged['HomeTeam'].notna().sum()
    logger.info(f"Matched {matched_count} / {len(merged)} records with external data")
    
    if matched_count < len(merged) * 0.9:
        logger.warning("Match rate is below 90%. Checking for common mismatches...")
        unmatched = merged[merged['HomeTeam'].isna()]
        
        # Identify which teams are causing mismatches
        unmatched_teams = unmatched['MatchHomeTeam'].unique()
        logger.warning(f"Teams failing to match (MatchHomeTeam): {unmatched_teams}")
        
        sample_unmatched = unmatched[['date_norm', 'MatchHomeTeam', 'team', 'opponent', 'is_home']].head(10)
        logger.warning(f"Sample unmatched rows:\n{sample_unmatched}")
    
    # Drop intermediate/redundant columns
    cols_to_drop = [
        'mapped_team', 'mapped_opponent', 'MatchHomeTeam', 'date_norm', 
        'Date', 'HomeTeam', 'AwayTeam'
    ]
    merged.drop(columns=[c for c in cols_to_drop if c in merged.columns], inplace=True)
    
    # Save
    merged.to_csv(OUTPUT_FILE, index=False)
    logger.info(f"Saved enriched dataset to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
