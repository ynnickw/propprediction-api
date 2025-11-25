import pandas as pd
import requests
from io import StringIO
import os

# 1. Get Football-Data.co.uk Team Names (2023/2024 Season)
url = "https://www.football-data.co.uk/mmz4281/2324/D1.csv"
print(f"Downloading {url}...")
resp = requests.get(url)
content = resp.content.decode('utf-8', errors='replace')
df_ext = pd.read_csv(StringIO(content))
ext_teams = sorted(df_ext['HomeTeam'].unique())

print("\n=== Football-Data.co.uk Teams (2023/2024) ===")
for t in ext_teams:
    print(f"'{t}'")

# 2. Get API-Football Team Names (from local data)
# We'll check the most recent file we have
local_file = "data/player_stats_Bundesliga_2023.csv"
if os.path.exists(local_file):
    df_local = pd.read_csv(local_file)
    api_teams = sorted(df_local['team'].unique())
    
    print("\n=== API-Football Teams (2023/2024) ===")
    for t in api_teams:
        print(f"'{t}'")
else:
    print(f"\n❌ Local file {local_file} not found. Cannot compare.")
