import pandas as pd
import os
import structlog
from datetime import datetime

logger = structlog.get_logger()

DATA_DIR = "data"

def load_player_metadata():
    """
    Load player profiles from Transfermarkt dataset.
    Returns a DataFrame with: player_id, name, position, height, age, is_striker, etc.
    """
    filepath = os.path.join(DATA_DIR, "player_profiles.csv")
    if not os.path.exists(filepath):
        logger.warning(f"Metadata file not found: {filepath}")
        return pd.DataFrame()

    logger.info("Loading player metadata...")
    try:
        df = pd.read_csv(filepath)
        
        # --- FILTER FOR BUNDESLIGA PLAYERS ---
        # 1. Load team competitions to identify Bundesliga teams
        team_comp_path = os.path.join(DATA_DIR, "team_competitions_seasons.csv")
        if os.path.exists(team_comp_path):
            team_df = pd.read_csv(team_comp_path)
            # Filter for Bundesliga (L1) in recent seasons (2023, 2024)
            bundesliga_teams = team_df[
                (team_df['competition_id'] == 'L1') & 
                (team_df['season_id'].isin([2023, 2024]))
            ]['club_id'].unique()
            
            # Filter players who are currently in these clubs
            initial_count = len(df)
            df = df[df['current_club_id'].isin(bundesliga_teams)]
            logger.info(f"Filtered for Bundesliga: {initial_count} -> {len(df)} players")
        else:
            logger.warning("Team competitions file not found, skipping Bundesliga filter")
        # -------------------------------------
        
        # Select relevant columns
        cols = [
            'player_id', 'player_name', 'position', 'height', 
            'date_of_birth', 'current_club_name', 'foot'
        ]
        # Handle missing columns gracefully
        available_cols = [c for c in cols if c in df.columns]
        df = df[available_cols].copy()
        
        # 1. Calculate Age
        if 'date_of_birth' in df.columns:
            df['date_of_birth'] = pd.to_datetime(df['date_of_birth'], errors='coerce')
            now = datetime.now()
            df['age'] = (now - df['date_of_birth']).dt.days / 365.25
            df['age'] = df['age'].fillna(25) # Default to 25 if unknown
            
        # 2. Position Grouping
        if 'position' in df.columns:
            # Create simplified position groups
            df['position_group'] = df['position'].apply(lambda x: 
                'Goalkeeper' if 'Goalkeeper' in str(x) else
                'Defender' if 'Defender' in str(x) else
                'Midfield' if 'Midfield' in str(x) else
                'Attack' if 'Attack' in str(x) or 'Winger' in str(x) or 'Forward' in str(x) else
                'Unknown'
            )
            
            # Specific flags
            df['is_striker'] = df['position'].str.contains('Attack|Forward|Winger', case=False, na=False).astype(int)
            df['is_defender'] = df['position'].str.contains('Defender', case=False, na=False).astype(int)
            df['is_midfielder'] = df['position'].str.contains('Midfield', case=False, na=False).astype(int)
            
        # 3. Height
        if 'height' in df.columns:
            df['height'] = pd.to_numeric(df['height'], errors='coerce').fillna(180) # Default 180cm

        # Rename for clarity
        df = df.rename(columns={'player_name': 'name'})
        
        logger.info(f"Loaded {len(df)} player profiles")
        return df

    except Exception as e:
        logger.error(f"Failed to load player metadata: {e}")
        return pd.DataFrame()

def load_market_values():
    """
    Load latest player market values.
    Returns DataFrame with: player_id, market_value_eur
    """
    filepath = os.path.join(DATA_DIR, "player_market_value.csv")
    if not os.path.exists(filepath):
        # Try alternate name if exists
        filepath = os.path.join(DATA_DIR, "player_latest_market_value.csv")
        if not os.path.exists(filepath):
            logger.warning("Market value file not found")
            return pd.DataFrame()

    logger.info("Loading market values...")
    try:
        df = pd.read_csv(filepath)
        
        # We want the LATEST value per player
        # If file is historical (date, value), sort and take last
        if 'date' in df.columns or 'date_unix' in df.columns:
            sort_col = 'date' if 'date' in df.columns else 'date_unix'
            df = df.sort_values(sort_col, ascending=False)
            df = df.drop_duplicates(subset=['player_id'], keep='first')
            
        # Ensure we have value column
        val_col = 'market_value_in_eur' if 'market_value_in_eur' in df.columns else 'value'
        if val_col in df.columns:
            df = df.rename(columns={val_col: 'market_value'})
            df['market_value'] = pd.to_numeric(df['market_value'], errors='coerce').fillna(0)
            
            return df[['player_id', 'market_value']]
            
        return pd.DataFrame()

    except Exception as e:
        logger.error(f"Failed to load market values: {e}")
        return pd.DataFrame()

def get_enriched_player_features():
    """
    Combine profiles and market values into a single feature set.
    """
    profiles = load_player_metadata()
    values = load_market_values()
    
    if profiles.empty:
        return pd.DataFrame()
        
    if not values.empty:
        # Merge on player_id
        profiles = pd.merge(profiles, values, on='player_id', how='left')
        profiles['market_value'] = profiles['market_value'].fillna(0)
        
    return profiles
