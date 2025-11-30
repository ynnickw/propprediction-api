# League IDs mapping (API Football)
LEAGUES = {
    "Bundesliga": 78,
}

# The Odds API Sport Keys
SPORT_KEYS = {
    "Bundesliga": "soccer_germany_bundesliga"
}

ODDS_API_TO_DB_MAPPING = {
    "Augsburg": "FC Augsburg",
    "Bayer Leverkusen": "Bayer Leverkusen",
    "Bayern Munich": "Bayern München",
    "Borussia Monchengladbach": "Borussia Mönchengladbach",
    "Darmstadt": "Darmstadt",
    "Freiburg": "SC Freiburg",
    "Greuther Furth": "Greuther Furth",
    "Hamburg": "Hamburger SV",
    "Heidenheim": "1. FC Heidenheim",
    "Hertha Berlin": "Hertha",
    "Hoffenheim": "1899 Hoffenheim",
    "Koln": "1. FC Köln",
    "Mainz": "FSV Mainz 05",
    "Nurnberg": "1. FC Nürnberg",
    "Schalke 04": "Schalke 04",
    "St. Pauli": "FC St. Pauli",
    "Stuttgart": "VfB Stuttgart",
    "Wolfsburg": "VfL Wolfsburg",
    "Bochum": "Bochum",
    "Dortmund": "Borussia Dortmund",
    "M'gladbach": "Borussia Mönchengladbach",
    "Arminia Bielefeld": "Bielefeld",
    "Werder Bremen": "Werder Bremen",
    "Union Berlin": "Union Berlin",
    "RB Leipzig": "RB Leipzig",
}

# API-Football to Database Team Name Mapping
# Maps team names from API-Football API to standardized names in the database
API_FOOTBALL_TO_DB_MAPPING = {
    # Bundesliga - Full names
    "FC Augsburg": "FC Augsburg",
    "Bayer Leverkusen": "Bayer Leverkusen",
    "Bayern Munich": "Bayern München",
    "Borussia Dortmund": "Borussia Dortmund",
    "Borussia Monchengladbach": "Borussia Mönchengladbach",
    "Borussia M'gladbach": "Borussia Mönchengladbach",
    "VfL Bochum": "Bochum",
    "Eintracht Frankfurt": "Eintracht Frankfurt",
    "SC Freiburg": "SC Freiburg",
    "Heidenheim": "1. FC Heidenheim",
    "TSG Hoffenheim": "1899 Hoffenheim",
    "Holstein Kiel": "Holstein Kiel",
    "FC Koln": "1. FC Köln",
    "RB Leipzig": "RB Leipzig",
    "Mainz": "FSV Mainz 05",
    "FC St. Pauli": "FC St. Pauli",
    "Union Berlin": "Union Berlin",
    "VfB Stuttgart": "VfB Stuttgart",
    "Werder Bremen": "Werder Bremen",
    "VfL Wolfsburg": "VfL Wolfsburg",
    
    # Bundesliga - Short name variations (to prevent duplicates)
    "Augsburg": "FC Augsburg",
    "Dortmund": "Borussia Dortmund",
    "Ein Frankfurt": "Eintracht Frankfurt",
    "Freiburg": "SC Freiburg",
    "Hamburg": "Hamburger SV",
    "Hoffenheim": "1899 Hoffenheim",
    "Leverkusen": "Bayer Leverkusen",
    "M'gladbach": "Borussia Mönchengladbach",
    "St Pauli": "FC St. Pauli",
    "Stuttgart": "VfB Stuttgart",
    "Wolfsburg": "VfL Wolfsburg",
}
