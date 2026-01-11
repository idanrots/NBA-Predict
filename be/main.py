import os
import json
import random
import requests
from datetime import datetime
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI()

# --- הגדרת CORS ---
# מאפשר לריאקט (localhost:5173) לדבר עם השרת הזה
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- מודל הנתונים שמגיע מהריאקט ---
class PredictionRequest(BaseModel):
    game_id: str
    date: str
    home_team: str
    away_team: str

# --- פונקציית MOCK (מייצרת נתונים באנגלית) ---
def generate_mock_prediction(home, away, game_id):
    """מייצרת תחזית דמה באנגלית כדי שהמערכת תעבוד לוקאלית"""
    print(f"⚠️  Generating MOCK data for {home} vs {away}...")
    
    # 1. בחירת מנצח רנדומלי
    winner = random.choice([home, away])
    confidence = random.randint(72, 98)
    
    # 2. יצירת תוצאה הגיונית
    score_winner = random.randint(108, 130)
    score_loser = score_winner - random.randint(2, 12)
    
    pred_home = score_winner if winner == home else score_loser
    pred_away = score_loser if winner == home else score_winner

    # 3. רשימת נימוקים באנגלית (באנגלית, כפי שביקשת)
    explanations = [
        f"The model identifies a clear advantage for {winner} in recent home games. The opponent's defensive stats are particularly weak in the fourth quarter.",
        f"Although {home} is strong, {away} arrives with positive momentum and high 3-point shooting percentages. The model predicts a close game decided in the final minutes.",
        f"The injury to the opponent's key star gives {winner} a significant advantage in the paint. A fast-paced game with high scoring is expected.",
        f"Matchup history shows clear superiority for {winner}. Additionally, their defense has been at its peak in the last five games.",
        f"Advanced metrics suggest {winner} has the edge due to superior rebounding and pace. {home if winner != home else away} has struggled against fast-break teams recently."
    ]

    return {
        "game_id": game_id,
        "predicted_winner": winner,
        "confidence": confidence,
        "explanation": random.choice(explanations), # בוחר נימוק רנדומלי מהרשימה
        "pred_home_score": pred_home,
        "pred_away_score": pred_away
    }

# --- Endpoints ---

@app.get("/games")
def get_games(date: str = Query(None)):
    """שליפת משחקים מ-ESPN (עובד ללא צורך ב-AWS)"""
    try:
        # טיפול בתאריך
        if date:
            target_date = date.replace('-', '')
        else:
            target_date = datetime.now().strftime('%Y%m%d')

        print(f"Fetching games for date: {target_date}")
        url = f"http://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={target_date}"
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
        
        if resp.status_code != 200:
            return []

        data = resp.json()
        formatted = []
        
        for event in data.get('events', []):
            competition = event['competitions'][0]
            competitors = competition['competitors']
            status_type = event['status']['type']
            
            home = next((x for x in competitors if x['homeAway'] == 'home'), {})
            away = next((x for x in competitors if x['homeAway'] == 'away'), {})
            
            # המרת סטטוס משחק
            status_state = status_type.get('state', '')
            my_status = 'Scheduled'
            if status_state == 'post': my_status = 'Final'
            elif status_state == 'in': my_status = 'Live'

            formatted.append({
                "gameId": event['id'],
                "time": status_type.get('shortDetail'),
                "status": my_status,
                "homeTeam": home.get('team', {}).get('displayName', 'Unknown'),
                "awayTeam": away.get('team', {}).get('displayName', 'Unknown'),
                "homeLogo": home.get('team', {}).get('logo', ''),
                "awayLogo": away.get('team', {}).get('logo', ''),
                "homeScore": int(home.get('score', 0)),
                "awayScore": int(away.get('score', 0))
            })
            
        return formatted

    except Exception as e:
        print(f"Error fetching games: {e}")
        return []

@app.post("/predict")
def predict(request: PredictionRequest):
    """
    נקודת הקצה לחיזוי.
    כרגע עוקפת את ה-DB וה-AWS ומחזירה תשובת Mock מיד.
    """
    return generate_mock_prediction(
        request.home_team, 
        request.away_team, 
        request.game_id
    )

if __name__ == "__main__":
    import uvicorn
    # הרצת השרת בפורט 8000
    uvicorn.run(app, host="0.0.0.0", port=8000)