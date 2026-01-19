import os
import json
import requests
import google.generativeai as genai
from datetime import datetime
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# --- טעינת משתני סביבה ---
load_dotenv()

# --- הגדרות ---
MY_API_KEY = os.getenv("GEMINI_API_KEY") or "הדבק_כאן_את_המפתח_שלך"

# --- הגדרת Gemini ---
model = None
try:
    if MY_API_KEY and "הדבק_כאן" not in MY_API_KEY:
        genai.configure(api_key=MY_API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash')
        print("✅ Gemini AI configured successfully")
    else:
        print("⚠️ Gemini AI skipped: Missing or invalid API Key")
except Exception as e:
    print(f"❌ Error configuring Gemini: {e}")

# --- חיבור ל-DB (בטוח לשימוש היברידי) ---
db = None
try:
    from db_handler import DBHandler
    db = DBHandler()
    print("✅ Database Handler Initialized")
except ImportError:
    print("⚠️ db_handler.py not found. Running in no-DB mode.")
except Exception as e:
    print(f"⚠️ Database connection failed: {e}")

# --- אתחול האפליקציה ---
app = FastAPI()

# --- הגדרת CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- מודל הנתונים ---
class PredictionRequest(BaseModel):
    game_id: str
    date: str
    home_team: str
    away_team: str

# --- פונקציות עזר ---
def clean_json_string(text):
    cleaned = text.strip()
    if cleaned.startswith("```json"): cleaned = cleaned[7:]
    if cleaned.startswith("```"): cleaned = cleaned[3:]
    if cleaned.endswith("```"): cleaned = cleaned[:-3]
    return cleaned.strip()

# --- Endpoints ---

@app.get("/games")
def get_games(date: str = Query(None)):
    """שליפת משחקים מ-ESPN"""
    try:
        if date:
            target_date = date.replace('-', '')
        else:
            target_date = datetime.now().strftime('%Y%m%d')

        url = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={target_date}"
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)

        if resp.status_code != 200:
            return []

        data = resp.json()
        events = data.get('events', [])
        formatted = []
        
        for event in events:
            competition = event['competitions'][0]
            competitors = competition['competitors']
            status_type = event['status']['type']
            
            home = next((x for x in competitors if x['homeAway'] == 'home'), {})
            away = next((x for x in competitors if x['homeAway'] == 'away'), {})
            
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
        print(f"❌ Error in get_games: {e}")
        return []

@app.get("/predictions/upcoming")
def get_upcoming_predictions():
    """מחזיר את 5 התחזיות הקרובות ביותר שקיימות ב-DB"""
    
    future_games = [] # אתחול מוקדם למניעת קריסה
    
    if not db:
        return []
    
    try:
        all_predictions = db.fetch_all_predictions() 

        today_str = datetime.now().strftime('%Y-%m-%d')
        
        for pred in all_predictions:
            game_date = pred.get('game_date')
            if game_date and game_date >= today_str:
                future_games.append(pred)

        future_games.sort(key=lambda x: x.get('game_date', '9999-12-31'))

        return future_games[:5]

    except Exception as e:
        print(f"❌ Error getting upcoming predictions: {e}")
        return []

@app.post("/predict")
def predict(request: PredictionRequest):
    """שליחת בקשה ל-Gemini AI עם שמירה ב-DB"""
    
    # 1. בדיקת Cache
    if db:
        try:
            cached = db.get_prediction(request.game_id)
            if cached:
                print("✅ Found in DB")
                cached.update({
                    'game_id': request.game_id,
                    'source': 'database',
                    'game_date': request.date,
                    'home_team': request.home_team,
                    'away_team': request.away_team
                })
                return cached
        except Exception as e:
            print(f"⚠️ DB Read Error: {e}")

    if not model:
        raise HTTPException(status_code=500, detail="AI Model not configured")

    print(f"🤖 Asking Gemini: {request.home_team} vs {request.away_team}...")

    prompt = f"""
    You are an expert NBA sports analyst. 
    Analyze the upcoming game between {request.home_team} (Home) and {request.away_team} (Away) on {request.date}.
    RETURN ONLY A RAW JSON OBJECT:
    {{
        "predicted_winner": "Team Name",
        "confidence": 85,
        "explanation": "Short analysis (max 2 sentences).",
        "pred_home_score": 110,
        "pred_away_score": 105
    }}
    """

    try:
        response = model.generate_content(prompt)
        clean_text = clean_json_string(response.text)
        prediction_data = json.loads(clean_text)
        
        prediction_data.update({
            'game_id': request.game_id,
            'source': 'ai',
            'game_date': request.date,
            'home_team': request.home_team,
            'away_team': request.away_team
        })
        
        if db:
            try:
                db.save_prediction(
                    game_id=request.game_id,
                    home=request.home_team,
                    away=request.away_team,
                    prediction_json=prediction_data
                )
                print("✅ Saved to DB")
            except Exception as e:
                print(f"⚠️ DB Save Error: {e}")

        return prediction_data

    except Exception as e:
        print(f"❌ Error: {e}")
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")

# --- הגדרת Handler עבור AWS Lambda ---
# אנו עוטפים את זה ב-try/except כדי שלא יקרוס לוקאלית אם mangum חסר
handler = None
try:
    from mangum import Mangum
    handler = Mangum(app)
except ImportError:
    print("⚠️ Mangum not found - skipping Lambda handler creation (OK for local dev)")

# --- הרצה לוקאלית ---
if __name__ == "__main__":
    import uvicorn
    # אם אתה רואה את ההודעה הזו - סימן שהקובץ תקין
    print("🚀 Starting Local Server on Port 8000...")
    uvicorn.run(app, host="0.0.0.0", port=8000)