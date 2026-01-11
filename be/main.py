import os
import json
import boto3
import requests
import psycopg2
from datetime import datetime
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from botocore.exceptions import ClientError

# --- קונפיגורציה ---

# הגדרות התחברות ל-DB (מושך ממשתני סביבה, או ברירת מחדל ללוקאלי)
DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "database": os.environ.get("DB_NAME", "postgres"),
    "user": os.environ.get("DB_USER", "postgres"),
    "password": os.environ.get("DB_PASS", "your_password"),
    "port": os.environ.get("DB_PORT", "5432")
}

# הגדרת המודל של קלוד (Bedrock)
# Haiku הוא המהיר והזול ביותר, Sonnet חכם יותר. לבחירתך.
BEDROCK_MODEL_ID = "anthropic.claude-3-haiku-20240307-v1:0" 
REGION_NAME = "us-east-1"

# --- אתחול האפליקציה ---

app = FastAPI()

# הגדרת CORS (חובה כדי שהפרונט יוכל לדבר עם הבקנד)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # מאפשר גישה מכל מקום (Amplify/Localhost)
    allow_methods=["*"],
    allow_headers=["*"],
)

# לקוח AWS Bedrock
try:
    bedrock = boto3.client(service_name='bedrock-runtime', region_name=REGION_NAME)
except Exception as e:
    print(f"Warning: Could not connect to Bedrock locally: {e}")
    bedrock = None

# --- פונקציות עזר ---

def get_db_connection():
    """יצירת חיבור למסד הנתונים"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        print(f"Database connection error: {e}")
        # בפיתוח לוקאלי לפעמים אין DB, לא נרצה להקריס את האפליקציה מיד
        return None

def clean_ai_json(text_response):
    """מנקה את הטקסט שחוזר מה-AI כדי לוודא שזה JSON תקין"""
    try:
        start = text_response.find('{')
        end = text_response.rfind('}') + 1
        if start != -1 and end != 0:
            return text_response[start:end]
        return text_response
    except Exception:
        return text_response

# --- Endpoints ---

@app.get("/")
def health_check():
    return {"status": "ok", "message": "NBA Predictor Backend is running"}

@app.get("/games")
def get_daily_games(date: str = Query(None)):
    try:
        # ברירת מחדל: היום
        target_date = datetime.now().strftime('%Y%m%d')

        if date:
            # === התיקון הקריטי ===
            # הופך את "2025-01-08" ל-"20250108"
            target_date = date.replace('-', '')
        
        print(f"DEBUG: Fetching from ESPN for date: {target_date}", flush=True)

        # הכתובת כעת תקבל את המספר הנקי ללא מקפים
        url = f"http://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={target_date}"
        
        headers = {
            "User-Agent": "Mozilla/5.0"
        }

        response = requests.get(url, headers=headers, timeout=5)
        
        if response.status_code != 200:
            print(f"ESPN Error: {response.status_code}")
            return []

        data = response.json()
        formatted_games = []
        
        events = data.get('events', [])
        
        for event in events:
            competition = event['competitions'][0]
            competitors = competition['competitors']
            
            home_team = next((x for x in competitors if x['homeAway'] == 'home'), {})
            away_team = next((x for x in competitors if x['homeAway'] == 'away'), {})
            
            # בדיקת סטטוס (pre/in/post)
            status_state = event['status']['type']['state']
            if status_state == 'pre':
                status_id = 1
            elif status_state == 'in':
                status_id = 2
            else:
                status_id = 3

            formatted_games.append({
                "gameId": event['id'],
                "homeTeam": home_team.get('team', {}).get('displayName', 'Unknown'),
                "awayTeam": away_team.get('team', {}).get('displayName', 'Unknown'),
                "time": event['status']['type']['shortDetail'],
                "statusId": status_id,
                "homeScore": int(home_team.get('score', 0)),
                "awayScore": int(away_team.get('score', 0))
            })

        return formatted_games

    except Exception as e:
        print(f"Error fetching games: {e}", flush=True)
        return []

@app.get("/predict/{game_id}")
def predict_game(game_id: str, home: str, away: str):
    """
    חיזוי משחק: DB -> אם אין אז AI -> שמירה ב-DB
    """
    conn = get_db_connection()
    
    # 1. ניסיון לשליפה מה-DB
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT prediction_json FROM game_predictions WHERE game_id = %s", (game_id,))
            existing = cursor.fetchone()
            if existing:
                print(f"💰 Loaded prediction from DB for {game_id}")
                return json.loads(existing[0])
            cursor.close()
        except Exception as e:
            print(f"DB Fetch Error: {e}")
            # ממשיכים ל-AI גם אם ה-DB נכשל רגעית

    # 2. יצירת חיזוי עם AI
    try:
        if not bedrock:
            raise HTTPException(status_code=503, detail="Bedrock client not initialized")

        print(f"🤖 Generating AI prediction: {home} vs {away}")
        
        prompt = f"""
        Act as an NBA expert analyst.
        Analyze the upcoming game: {home} (Home) vs {away} (Away).
        
        Return a valid JSON object with:
        - "winner": The predicted winning team name.
        - "confidence": A number 50-100.
        - "reasoning": A short explanation in Hebrew (2 sentences).
        
        Output ONLY the JSON. No markdown, no pre-text.
        """

        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 300,
            "messages": [{"role": "user", "content": prompt}]
        })

        response = bedrock.invoke_model(
            modelId=BEDROCK_MODEL_ID,
            body=body
        )
        
        response_body = json.loads(response['body'].read())
        ai_text = response_body['content'][0]['text']
        clean_json_str = clean_ai_json(ai_text)
        prediction_data = json.loads(clean_json_str)

        # 3. שמירה ב-DB
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO game_predictions (game_id, home_team, away_team, prediction_json) VALUES (%s, %s, %s, %s)",
                    (game_id, home, away, clean_json_str)
                )
                conn.commit()
                cursor.close()
            except Exception as e:
                print(f"DB Save Error: {e}")
                conn.rollback()
        
        return prediction_data

    except Exception as e:
        print(f"Prediction Error: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate prediction")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)