import os
import json
import requests
import google.generativeai as genai
from datetime import datetime
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv  # <--- הוספנו את זה

# --- ייבוא ה-DB Handler ---
from db_handler import DBHandler

# --- טעינת משתני הסביבה (טוען את קובץ .env) ---
load_dotenv()

# --- הגדרות ---

# 🛑 שליפת המפתח בצורה מאובטחת מה-env 🛑
MY_API_KEY = os.getenv("GEMINI_API_KEY")

if not MY_API_KEY:
    print("❌ Error: GEMINI_API_KEY not found in environment variables!")

# הגדרת המודל של ג'מיני
try:
    if MY_API_KEY:
        genai.configure(api_key=MY_API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash')
        print("✅ Gemini AI configured successfully")
    else:
        print("⚠️ Gemini AI skipped due to missing API Key")
except Exception as e:
    print(f"❌ Error configuring Gemini: {e}")

# --- אתחול החיבור ל-DB ---
try:
    db = DBHandler()
    print("✅ Database Handler Initialized")
except Exception as e:
    print(f"⚠️ Warning: DB Handler failed to init: {e}")
    db = None

app = FastAPI()

# הגדרת CORS
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
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    if cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
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

        # הוספתי כאן את התיקון ל-URL שעשינו קודם
        url = f"http://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={target_date}"
        
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5)

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

@app.post("/predict")
def predict(request: PredictionRequest):
    """שליחת בקשה ל-Gemini AI עם שמירה ב-DB"""
    
    # 1. בדיקה האם כבר קיים חיזוי ב-DB
    if db:
        print(f"🔍 Checking DB for game: {request.game_id}...")
        cached_prediction = db.get_prediction(request.game_id)
        if cached_prediction:
            print("✅ Found prediction in DB! Returning cached result.")
            cached_prediction['game_id'] = request.game_id
            cached_prediction['source'] = 'database'
            return cached_prediction

    print(f"🤖 Asking Gemini to predict: {request.home_team} vs {request.away_team}...")

    prompt = f"""
    You are an expert NBA sports analyst. 
    Analyze the upcoming game between {request.home_team} (Home) and {request.away_team} (Away) on {request.date}.
    
    Consider:
    1. Team form and recent performance.
    2. Home court advantage.
    3. Key player injuries (use your general knowledge).
    4. Head-to-head match-ups.

    RETURN ONLY A RAW JSON OBJECT (no markdown formatting). 
    The JSON must match this structure exactly:
    {{
        "predicted_winner": "Team Name",
        "confidence": 85,
        "explanation": "A professional, sharp analysis reason in English (max 2 sentences).",
        "pred_home_score": 110,
        "pred_away_score": 105
    }}
    """

    try:
        response = model.generate_content(prompt)
        clean_text = clean_json_string(response.text)
        prediction_data = json.loads(clean_text)
        prediction_data['game_id'] = request.game_id
        prediction_data['source'] = 'ai'
        
        # 2. שמירת התוצאה ב-DB
        if db:
            print(f"💾 Saving prediction to DB for game: {request.game_id}...")
            db.save_prediction(
                game_id=request.game_id,
                home=request.home_team,
                away=request.away_team,
                prediction_json=prediction_data
            )
            print("✅ Saved successfully.")

        return prediction_data

    except Exception as e:
        print(f"❌ Gemini/DB Error: {e}")
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)