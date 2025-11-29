import asyncio
import sys
import os
import pandas as pd
import requests
from io import StringIO
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.infrastructure.db.session import SessionLocal, engine, Base
from app.domain.models import Match, Team
from sqlalchemy import select, text

# League mapping
LEAGUES = {
    'E0': 'Premier League',
    'SP1': 'La Liga',
    'D1': 'Bundesliga'
}

# Seasons to import (2020/2021 to 2024/2025)
SEASONS = ['2021', '2122', '2223', '2324', '2425', '2526']

BASE_URL = "https://www.football-data.co.uk/mmz4281/{}/{}.csv"

async def get_or_create_team(session, team_name, league):
    stmt = select(Team).where(Team.name == team_name)
    result = await session.execute(stmt)
    team = result.scalar_one_or_none()
    
    if not team:
        team = Team(name=team_name, league=league)
        session.add(team)
        await session.flush() # Get ID
        print(f"Created team: {team_name}")
    
    return team

async def import_data():
    # Recreate tables (WARNING: DELETES DATA)
    print("Recreating tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    
    async with SessionLocal() as session:
        for season in SEASONS:
            for league_code, league_name in LEAGUES.items():
                url = BASE_URL.format(season, league_code)
                print(f"Downloading {league_name} {season} from {url}...")
                
                try:
                    response = requests.get(url)
                    response.raise_for_status()
                    
                    # Read CSV
                    csv_data = StringIO(response.text)
                    df = pd.read_csv(csv_data)
                    
                    print(f"Processing {len(df)} matches...")
                    
                    for _, row in df.iterrows():
                        # Parse date
                        try:
                            date_str = row['Date']
                            # Handle different date formats
                            if len(date_str) == 8: # DD/MM/YY
                                match_date = datetime.strptime(date_str, "%d/%m/%y")
                            else: # DD/MM/YYYY
                                match_date = datetime.strptime(date_str, "%d/%m/%Y")
                                
                            # Add time if available
                            if 'Time' in row and pd.notna(row['Time']):
                                time_str = row['Time']
                                hour, minute = map(int, time_str.split(':'))
                                match_date = match_date.replace(hour=hour, minute=minute)
                            else:
                                # Default to 15:00 if no time
                                match_date = match_date.replace(hour=15, minute=0)
                                
                        except Exception as e:
                            print(f"Error parsing date {row.get('Date')}: {e}")
                            continue
                        
                        home_team_name = row['HomeTeam']
                        away_team_name = row['AwayTeam']
                        
                        # Get teams
                        home_team = await get_or_create_team(session, home_team_name, league_name)
                        away_team = await get_or_create_team(session, away_team_name, league_name)
                        
                        # Create Match
                        match = Match(
                            league_id={'E0': 1, 'SP1': 2, 'D1': 3}.get(league_code, 0),
                            home_team_id=home_team.id,
                            away_team_id=away_team.id,
                            start_time=match_date,
                            status='FT', # Assumed finished for historical data
                            
                            # Scores
                            home_score=int(row['FTHG']) if pd.notna(row.get('FTHG')) else None,
                            away_score=int(row['FTAG']) if pd.notna(row.get('FTAG')) else None,
                            home_half_time_goals=int(row['HTHG']) if pd.notna(row.get('HTHG')) else None,
                            away_half_time_goals=int(row['HTAG']) if pd.notna(row.get('HTAG')) else None,
                            
                            # Stats
                            home_shots=int(row['HS']) if pd.notna(row.get('HS')) else None,
                            away_shots=int(row['AS']) if pd.notna(row.get('AS')) else None,
                            home_shots_on_target=int(row['HST']) if pd.notna(row.get('HST')) else None,
                            away_shots_on_target=int(row['AST']) if pd.notna(row.get('AST')) else None,
                            home_corners=int(row['HC']) if pd.notna(row.get('HC')) else None,
                            away_corners=int(row['AC']) if pd.notna(row.get('AC')) else None,
                            home_fouls=int(row['HF']) if pd.notna(row.get('HF')) else None,
                            away_fouls=int(row['AF']) if pd.notna(row.get('AF')) else None,
                            home_yellow_cards=int(row['HY']) if pd.notna(row.get('HY')) else None,
                            away_yellow_cards=int(row['AY']) if pd.notna(row.get('AY')) else None,
                            home_red_cards=int(row['HR']) if pd.notna(row.get('HR')) else None,
                            away_red_cards=int(row['AR']) if pd.notna(row.get('AR')) else None,
                            
                            # Odds (Bet365)
                            odds_home=float(row['B365H']) if pd.notna(row.get('B365H')) else None,
                            odds_draw=float(row['B365D']) if pd.notna(row.get('B365D')) else None,
                            odds_away=float(row['B365A']) if pd.notna(row.get('B365A')) else None,
                            
                            # Market Odds
                            odds_over_2_5=float(row['B365>2.5']) if pd.notna(row.get('B365>2.5')) else None,
                            odds_under_2_5=float(row['B365<2.5']) if pd.notna(row.get('B365<2.5')) else None,
                            # BTTS odds are not always consistent in column names, checking common ones
                            odds_btts_yes=float(row['BbAvbbMxH']) if pd.notna(row.get('BbAvbbMxH')) else None, # Placeholder, need to check column names
                        )
                        
                        # BTTS columns vary by season/league in football-data.co.uk
                        # Common: BbAvBTTSY / BbAvBTTSN (BetBrain Average) or B365BTTSY
                        if 'B365BTTSY' in row and pd.notna(row['B365BTTSY']):
                             match.odds_btts_yes = float(row['B365BTTSY'])
                             match.odds_btts_no = float(row['B365BTTSN'])
                        
                        session.add(match)
                    
                    await session.commit()
                    print(f"Imported {league_name} {season}")
                    
                except Exception as e:
                    print(f"Error importing {league_name} {season}: {e}")

if __name__ == "__main__":
    asyncio.run(import_data())
