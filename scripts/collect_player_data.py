"""
Collect real player-level statistics from API-Football.

This script fetches historical player match statistics and saves them
to a CSV file for model training.

Usage:
    docker-compose run --rm backend python -m app.collect_player_data
"""

import requests
import pandas as pd
import os
import time
from datetime import datetime
from dotenv import load_dotenv
import structlog

logger = structlog.get_logger()

load_dotenv()

API_KEY = os.getenv('API_FOOTBALL_KEY')
BASE_URL = "https://v3.football.api-sports.io/"
DATA_DIR = "data"

# League IDs - Focus on Bundesliga
LEAGUES = {
    'Bundesliga': 78
}

def fetch_with_retry(url: str, headers: dict, params: dict, max_retries: int = 3) -> dict:
    """Fetch data with retry logic for rate limiting."""
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers, params=params)
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                wait_time = 60 * (attempt + 1)
                logger.warning(f"Rate limited, waiting {wait_time}s...")
                time.sleep(wait_time)
            else:
                response.raise_for_status()
        except Exception as e:
            logger.error(f"Request failed: {e}")
            if attempt == max_retries - 1:
                raise
            time.sleep(5)
    
    raise Exception("Max retries exceeded")

# ... (lines 26-56)

def fetch_fixtures(league_id: int, season: int) -> list:
    """Fetch all fixtures for a league and season."""
    url = f"{BASE_URL}/fixtures"
    headers = {
        'x-apisports-key': API_KEY
    }
    params = {
        'league': league_id,
        'season': season
    }
    
    logger.info(f"Fetching fixtures for league {league_id}, season {season}")
    data = fetch_with_retry(url, headers, params)
    
    # DEBUG: Print raw response if empty
    if not data.get('response'):
        logger.info(f"RAW RESPONSE: {data}")
    
    fixtures = data.get('response', [])
    logger.info(f"Found {len(fixtures)} fixtures")
    
    return fixtures

def fetch_player_stats_for_fixture(fixture_id: int) -> list:
    """Fetch player statistics for a specific fixture."""
    url = f"{BASE_URL}/fixtures/players"
    headers = {
        'x-apisports-key': API_KEY
    }
    params = {'fixture': fixture_id}
    
    data = fetch_with_retry(url, headers, params)
    return data.get('response', [])

def extract_player_data(fixture: dict, team_data: dict) -> list:
    """Extract player statistics from fixture data."""
    fixture_date = fixture['fixture']['date']
    fixture_id = fixture['fixture']['id']
    
    home_team = fixture['teams']['home']['name']
    away_team = fixture['teams']['away']['name']
    team_name = team_data['team']['name']
    
    is_home = 1 if team_name == home_team else 0
    opponent = away_team if is_home else home_team
    
    player_records = []
    
    for player_data in team_data['players']:
        player = player_data['player']
        stats = player_data['statistics'][0] if player_data['statistics'] else {}
        
        # Extract comprehensive statistics
        games = stats.get('games', {})
        shots_data = stats.get('shots', {})
        goals_data = stats.get('goals', {})
        passes_data = stats.get('passes', {})
        tackles_data = stats.get('tackles', {})
        duels_data = stats.get('duels', {})
        dribbles_data = stats.get('dribbles', {})
        fouls_data = stats.get('fouls', {})
        cards_data = stats.get('cards', {})
        
        minutes = games.get('minutes', 0)
        position = games.get('position', 'Unknown')
        rating = games.get('rating', None)
        
        # Only include players who actually played
        if minutes and minutes > 0:
            player_records.append({
                'fixture_id': fixture_id,
                'date': fixture_date,
                'player_id': player['id'],
                'player_name': player['name'],
                'team': team_name,
                'opponent': opponent,
                'is_home': is_home,
                'position': position,
                'minutes': minutes,
                'rating': float(rating) if rating else None,
                
                # Shooting stats
                'shots': shots_data.get('total', 0) or 0,
                'shots_on_target': shots_data.get('on', 0) or 0,
                
                # Scoring stats
                'goals': goals_data.get('total', 0) or 0,
                'assists': goals_data.get('assists', 0) or 0,
                
                # Passing stats
                'passes': passes_data.get('total', 0) or 0,
                'passes_accurate': passes_data.get('accuracy', 0) or 0,
                'key_passes': passes_data.get('key', 0) or 0,
                
                # Defensive stats
                'tackles': tackles_data.get('total', 0) or 0,
                'blocks': tackles_data.get('blocks', 0) or 0,
                'interceptions': tackles_data.get('interceptions', 0) or 0,
                
                # Duel stats
                'duels_total': duels_data.get('total', 0) or 0,
                'duels_won': duels_data.get('won', 0) or 0,
                
                # Dribbling stats
                'dribbles_attempts': dribbles_data.get('attempts', 0) or 0,
                'dribbles_success': dribbles_data.get('success', 0) or 0,
                
                # Discipline
                'fouls_drawn': fouls_data.get('drawn', 0) or 0,
                'fouls_committed': fouls_data.get('committed', 0) or 0,
                'yellow_cards': cards_data.get('yellow', 0) or 0,
                'red_cards': cards_data.get('red', 0) or 0,
                'cards': (cards_data.get('yellow', 0) or 0) + (cards_data.get('red', 0) or 0)
            })
    
    return player_records

def collect_league_season_data(league_id: int, season: int, max_fixtures: int = None) -> pd.DataFrame:
    """Collect all player data for a league and season."""
    fixtures = fetch_fixtures(league_id, season)
    
    if max_fixtures:
        fixtures = fixtures[:max_fixtures]
        logger.info(f"Limited to {max_fixtures} fixtures for testing")
    
    all_player_data = []
    
    for i, fixture in enumerate(fixtures):
        fixture_id = fixture['fixture']['id']
        fixture_status = fixture['fixture']['status']['short']
        
        # Only process finished matches
        if fixture_status != 'FT':
            continue
        
        logger.info(f"Processing fixture {i+1}/{len(fixtures)}: {fixture_id}")
        
        try:
            player_stats = fetch_player_stats_for_fixture(fixture_id)
            
            for team_data in player_stats:
                player_records = extract_player_data(fixture, team_data)
                all_player_data.extend(player_records)
            
            # Rate limiting: Pro Plan allows higher throughput
            # Reduce delay to 0.2s
            time.sleep(0.2)
            
        except Exception as e:
            logger.error(f"Failed to process fixture {fixture_id}: {e}")
            continue
    
    df = pd.DataFrame(all_player_data)
    logger.info(f"Collected {len(df)} player-match records")
    
    return df

def main():
    """Main data collection workflow."""
    logger.info("Starting Bundesliga player data collection")
    logger.info("Focus: Comprehensive Bundesliga data (2020-2024)")
    
    if not API_KEY:
        logger.error("API_FOOTBALL_KEY not found in environment variables")
        return
    
    os.makedirs(DATA_DIR, exist_ok=True)
    
    all_data = []
    
    # Collect comprehensive Bundesliga data across multiple seasons
    league_name = 'Bundesliga'
    league_id = LEAGUES[league_name]
    
    # Collect comprehensive history (Pro Plan: 2020-2024)
    seasons = [2025]
    
    for season in seasons:
        logger.info(f"\n{'='*60}")
        logger.info(f"Collecting {league_name} - {season}/{season+1}")
        logger.info(f"{'='*60}\n")
        
        try:
            # Collect ALL fixtures (no max_fixtures limit)
            df = collect_league_season_data(
                league_id, 
                season,
                max_fixtures=None  # Collect all fixtures
            )
            
            if not df.empty:
                all_data.append(df)
                
                # Save intermediate results
                intermediate_path = os.path.join(
                    DATA_DIR, 
                    f'player_stats_{league_name}_{season}.csv'
                )
                df.to_csv(intermediate_path, index=False)
                logger.info(f"Saved intermediate data to {intermediate_path}")
            
        except Exception as e:
            logger.error(f"Failed to collect {league_name} {season}: {e}")
            continue
    
    if not all_data:
        logger.error("No data collected")
        return
    
    # Combine all data
    combined = pd.concat(all_data, ignore_index=True)
    
    # Convert date to datetime
    combined['date'] = pd.to_datetime(combined['date'])
    
    # Sort by player and date
    combined = combined.sort_values(['player_id', 'date'])
    
    # Remove duplicates (in case of data issues)
    combined = combined.drop_duplicates(subset=['fixture_id', 'player_id'])
    
    # Save final dataset
    output_path = os.path.join(DATA_DIR, 'player_stats_history.csv')
    combined.to_csv(output_path, index=False)
    
    logger.info(f"\n{'='*60}")
    logger.info(f"✅ Bundesliga data collection complete!")
    logger.info(f"{'='*60}")
    logger.info(f"Total records: {len(combined)}")
    logger.info(f"Unique players: {combined['player_id'].nunique()}")
    logger.info(f"Unique fixtures: {combined['fixture_id'].nunique()}")
    logger.info(f"Date range: {combined['date'].min()} to {combined['date'].max()}")
    logger.info(f"Seasons covered: {len(seasons)}")
    logger.info(f"Saved to: {output_path}")
    
    # Display sample statistics
    logger.info(f"\n📊 Bundesliga Statistics:")
    logger.info(f"Average shots per match: {combined['shots'].mean():.2f}")
    logger.info(f"Average shots on target: {combined['shots_on_target'].mean():.2f}")
    logger.info(f"Average assists: {combined['assists'].mean():.2f}")
    logger.info(f"Average minutes: {combined['minutes'].mean():.2f}")
    logger.info(f"Average goals: {combined['goals'].mean():.2f}")
    
    # Top players by shots
    logger.info(f"\n⚽ Top 10 Players by Total Shots:")
    top_shooters = combined.groupby('player_name')['shots'].sum().sort_values(ascending=False).head(10)
    for i, (player, shots) in enumerate(top_shooters.items(), 1):
        logger.info(f"{i}. {player}: {shots} shots")

if __name__ == "__main__":
    main()
