import os
import sys
import pandas as pd
from pathlib import Path
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Add app to path
sys.path.insert(0, str(Path(__file__).parent.parent))

load_dotenv()

DATA_DIR = "data"

def get_db_engine():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL not set")
    
    if database_url.startswith("postgresql+asyncpg"):
        database_url = database_url.replace("postgresql+asyncpg", "postgresql")
    
    if "host.docker.internal" in database_url:
        database_url = database_url.replace("host.docker.internal", "localhost")
        
    return create_engine(database_url)

# Helper functions
def safe_int(val):
    try:
        if pd.isna(val):
            return None
        return int(float(val))
    except (ValueError, TypeError):
        return None

def safe_float(val):
    try:
        if pd.isna(val):
            return None
        return float(val)
    except (ValueError, TypeError):
        return None

def seed_scores():
    engine = get_db_engine()
    
    # Load all CSVs
    years = [2020, 2021, 2022, 2023, 2024, 2025]
    dfs = []
    for year in years:
        file_path = os.path.join(DATA_DIR, f"D1_{year}.csv")
        if os.path.exists(file_path):
            print(f"Loading {file_path}...")
            df = pd.read_csv(file_path)
            dfs.append(df)
    
    if not dfs:
        print("No data files found.")
        return

    combined_df = pd.concat(dfs, ignore_index=True)
    print(f"Loaded {len(combined_df)} records from CSVs.")
    
    # Ensure date format matches DB (assuming DB has timestamps)
    # CSV Date format is usually DD/MM/YYYY
    combined_df['Date'] = pd.to_datetime(combined_df['Date'], format='%d/%m/%Y', errors='coerce')
    
    # CSV Team -> DB Team Mapping
    team_mapping = {
        'Augsburg': 'FC Augsburg',
        'Bayer Leverkusen': 'Bayer Leverkusen',
        'Bayern Munich': 'Bayern München',
        'Bielefeld': 'Arminia Bielefeld',
        'Bochum': 'VfL Bochum',
        'Darmstadt': 'SV Darmstadt 98',
        'Dortmund': 'Borussia Dortmund',
        'Ein Frankfurt': 'Eintracht Frankfurt',
        'FC Koln': '1. FC Köln',
        'Freiburg': 'SC Freiburg',
        'Greuther Furth': 'SpVgg Greuther Furth',
        'Hamburg': 'Hamburger SV',
        'Heidenheim': '1. FC Heidenheim',
        'Hertha': 'Hertha Berlin',
        'Hoffenheim': '1899 Hoffenheim',
        'Holstein Kiel': 'Holstein Kiel',
        'Leverkusen': 'Bayer Leverkusen',
        "M'gladbach": 'Borussia Mönchengladbach',
        'Mainz': 'FSV Mainz 05',
        'RB Leipzig': 'RB Leipzig',
        'Schalke 04': 'FC Schalke 04',
        'St Pauli': 'FC St. Pauli',
        'Stuttgart': 'VfB Stuttgart',
        'Union Berlin': 'Union Berlin',
        'Werder Bremen': 'Werder Bremen',
        'Wolfsburg': 'VfL Wolfsburg',
        'Fortuna Dusseldorf': 'Fortuna Dusseldorf', # Verify if in DB
        'Paderborn': 'SC Paderborn 07', # Verify
    }

    updated_count = 0
    
    with engine.connect() as conn:
        print("Updating matches in DB...")
        
        for _, row in combined_df.iterrows():
            if pd.isna(row['Date']) or pd.isna(row['FTHG']) or pd.isna(row['FTAG']):
                continue
                
            csv_home = row['HomeTeam']
            csv_away = row['AwayTeam']
            
            # Map teams
            db_home = team_mapping.get(csv_home, csv_home)
            db_away = team_mapping.get(csv_away, csv_away)
            
            match_date = row['Date'].date()
            
            # Scores
            home_score = safe_int(row.get('FTHG'))
            away_score = safe_int(row.get('FTAG'))
            home_half_time_goals = safe_int(row.get('HTHG'))
            away_half_time_goals = safe_int(row.get('HTAG'))
            
            # Detailed stats
            home_shots = safe_int(row.get('HS'))
            away_shots = safe_int(row.get('AS'))
            home_shots_on_target = safe_int(row.get('HST'))
            away_shots_on_target = safe_int(row.get('AST'))
            home_corners = safe_int(row.get('HC'))
            away_corners = safe_int(row.get('AC'))
            home_fouls = safe_int(row.get('HF'))
            away_fouls = safe_int(row.get('AF'))
            home_yellow_cards = safe_int(row.get('HY'))
            away_yellow_cards = safe_int(row.get('AY'))
            home_red_cards = safe_int(row.get('HR'))
            away_red_cards = safe_int(row.get('AR'))
            
            # Odds
            # Odds
            # Odds
            odds_home = safe_float(row.get('B365H'))
            odds_draw = safe_float(row.get('B365D'))
            odds_away = safe_float(row.get('B365A'))
            odds_over_2_5 = safe_float(row.get('B365>2.5'))
            odds_under_2_5 = safe_float(row.get('B365<2.5'))
            
            # Update query
            stmt = text("""
                UPDATE matches 
                SET home_score = :home_score, 
                    away_score = :away_score,
                    home_half_time_goals = :home_half_time_goals,
                    away_half_time_goals = :away_half_time_goals,
                    home_shots = :home_shots,
                    away_shots = :away_shots,
                    home_shots_on_target = :home_shots_on_target,
                    away_shots_on_target = :away_shots_on_target,
                    home_corners = :home_corners,
                    away_corners = :away_corners,
                    home_fouls = :home_fouls,
                    away_fouls = :away_fouls,
                    home_yellow_cards = :home_yellow_cards,
                    away_yellow_cards = :away_yellow_cards,
                    home_red_cards = :home_red_cards,
                    away_red_cards = :away_red_cards,
                    odds_home = :odds_home,
                    odds_draw = :odds_draw,
                    odds_away = :odds_away,
                    odds_over_2_5 = :odds_over_2_5,
                    odds_under_2_5 = :odds_under_2_5
                WHERE (home_team = :db_home OR home_team = :csv_home)
                  AND (away_team = :db_away OR away_team = :csv_away)
                  AND DATE(start_time) = :match_date
            """)
            
            result = conn.execute(stmt, {
                "home_score": home_score,
                "away_score": away_score,
                "home_half_time_goals": home_half_time_goals,
                "away_half_time_goals": away_half_time_goals,
                "home_shots": home_shots,
                "away_shots": away_shots,
                "home_shots_on_target": home_shots_on_target,
                "away_shots_on_target": away_shots_on_target,
                "home_corners": home_corners,
                "away_corners": away_corners,
                "home_fouls": home_fouls,
                "away_fouls": away_fouls,
                "home_yellow_cards": home_yellow_cards,
                "away_yellow_cards": away_yellow_cards,
                "home_red_cards": home_red_cards,
                "away_red_cards": away_red_cards,
                "odds_home": odds_home,
                "odds_draw": odds_draw,
                "odds_away": odds_away,
                "odds_over_2_5": odds_over_2_5,
                "odds_under_2_5": odds_under_2_5,
                "db_home": db_home,
                "csv_home": csv_home,
                "db_away": db_away,
                "csv_away": csv_away,
                "match_date": match_date
            })
            
            updated_count += result.rowcount
            
        conn.commit()
        
    print(f"Updated {updated_count} matches with scores, stats, and odds.")

if __name__ == "__main__":
    seed_scores()
