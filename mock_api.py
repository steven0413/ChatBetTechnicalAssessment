from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime, timedelta
import random
import uuid
from typing import List, Dict, Optional

app = FastAPI(title="Mock Sports API", version="1.0.0")

# Habilitar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Datos mock
sports_data = [
    {"id": 1, "name": "Football", "icon": "⚽"},
    {"id": 2, "name": "Basketball", "icon": "🏀"},
]

teams_data = {
    "football": [
        {"id": 1, "name": "Barcelona", "country": "Spain"},
        {"id": 2, "name": "Real Madrid", "country": "Spain"},
        {"id": 3, "name": "Bayern Munich", "country": "Germany"},
        {"id": 4, "name": "Juventus", "country": "Italy"},
    ]
}

tournaments_data = [
    {"id": 1, "name": "Champions League", "sport_id": 1},
    {"id": 2, "name": "La Liga", "sport_id": 1},
    {"id": 3, "name": "Premier League", "sport_id": 1},
]

# Generar partidos de ejemplo
def generate_fixtures():
    fixtures = []
    today = datetime.now()
    football_teams = teams_data["football"]
    
    # Partidos de fútbol
    for i in range(10):
        match_date = today + timedelta(days=random.randint(0, 7))
        team1 = random.choice(football_teams)
        team2 = random.choice([t for t in football_teams if t["id"] != team1["id"]])
        
        fixtures.append({
            "id": i + 1,
            "sport_id": 1,
            "tournament_id": random.choice([1, 2, 3]),
            "team_home": team1["name"],
            "team_away": team2["name"],
            "date": match_date.strftime("%Y-%m-%d"),
            "time": f"{random.randint(12, 22)}:00",
            "location": f"Stadium {random.randint(1, 10)}"
        })
    
    return fixtures

fixtures_data = generate_fixtures()

# Generar odds de ejemplo
def generate_odds():
    odds = []
    for fixture in fixtures_data:
        # Odds para resultado del partido (1-X-2)
        home_win = round(random.uniform(1.5, 3.0), 2)
        draw = round(random.uniform(2.0, 4.0), 2)
        away_win = round(random.uniform(1.5, 3.5), 2)
        
        odds.append({
            "fixture_id": fixture["id"],
            "market": "match_result",
            "home_win": home_win,
            "draw": draw,
            "away_win": away_win,
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
    
    return odds

odds_data = generate_odds()

# Endpoints de deportes
@app.get("/sports")
async def get_sports():
    return sports_data

@app.get("/sports/fixtures")
async def get_fixtures(date: Optional[str] = None):
    result = fixtures_data
    if date:
        result = [f for f in result if f["date"] == date]
    return result

@app.get("/sports/odds")
async def get_odds(fixture_id: Optional[int] = None):
    if fixture_id:
        return [o for o in odds_data if o["fixture_id"] == fixture_id]
    return odds_data

@app.get("/")
async def root():
    return {"message": "Mock Sports API is running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)