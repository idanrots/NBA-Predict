import os
import json
import boto3
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# NBA API Imports - stats מיועד לנתונים היסטוריים ועתידיים יציבים
from nba_api.stats.endpoints import scoreboardv2
from nba_api.stats.static import teams

# ייבוא ה-Handler שיצרנו
from db_handler import DBHandler

# אתחול האפליקציה וה-DB
app = FastAPI()
db = DBHandler()

# הגדרות CORS - מאפשר לפרונט (React) לתקשר עם הבקנד
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# אתחול הגישה ל-AI של AWS
bedrock = boto3.client(service_name='bedrock-runtime', region_name='us-east-1')

# טעינת מפת שמות הקבוצות פעם אחת בזיכרון (ייעול ביצועים)
nba_teams = teams.get_teams()
teams_map = {team['id']: team['full_name'] for team in nba_teams}

@app.get("/games")
def get_daily_games(date: str = None):
    """
    שליפת משחקים לפי תאריך.
    משתמש ב-scoreboardv2 לקבלת נתונים אמינים.
    """
    try:
        # אם לא סופק תאריך מהפרונט, משתמשים בתאריך של היום
        if not date:
            date = datetime.now().strftime('%Y-%m-%d')
            
        # פנייה ל-API של ה-NBA
        board = scoreboardv2.ScoreBoardV2(game_date=date, league_id='00')
        game_headers = board.game_header.get_dict()['data']
        
        formatted_games = []
        for game in game_headers:
            status_id = game[3]
            
            # הצגת משחקים עתידיים בלבד (status_id == 1)
            if status_id == 1:
                formatted_games.append({
                    "gameId": game[2],
                    "homeTeam": teams_map.get(game[6], "Unknown"),
                    "awayTeam": teams_map.get(game[7], "Unknown"),
                    "time": game[4].strip(), # שעת המשחק בפורמט טקסט
                    "statusId": status_id
                })
        return formatted_games
    except Exception as e:
        print(f"Error fetching games: {e}")
        return []

@app.get("/predict/{game_id}")
def predict_game(game_id: str, home: str, away: str):
    """
    מנגנון חיזוי חכם:
    1. בודק ב-DB אם כבר יש חיזוי קיים (חוסך כסף וזמן).
    2. אם אין, פונה ל-AI (Claude 3) לקבלת ניתוח.
    3. שומר את התוצאה ב-DB לפעם הבאה.
    """
    try:
        # בדיקה ב-Database (ה"זיכרון" של המערכת)
        existing = db.get_prediction(game_id)
        if existing:
            print(f"💰 Token Saved! Returning prediction from DB for {game_id}")
            return existing

        # פנייה לבינה מלאכותית (Bedrock)
        print(f"🤖 Generating new AI prediction for {home} vs {away}...")
        prompt = f"""
        Act as an NBA expert. Analyze the game: {home} vs {away}.
        Provide a prediction in JSON format:
        - "winner": the team name.
        - "confidence": percentage (50-100).
        - "reasoning": 2 professional sentences in Hebrew.
        Return ONLY JSON.
        """
        
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 300,
            "messages": [{"role": "user", "content": prompt}]
        })

        response = bedrock.invoke_model(
            modelId="anthropic.claude-3-sonnet-20240229-v1:0", 
            body=body
        )
        
        # פענוח התשובה של ה-AI
        response_content = json.loads(response['body'].read())
        ai_text = response_content['content'][0]['text']
        
        # חילוץ ה-JSON מהטקסט של ה-AI
        start = ai_text.find('{')
        end = ai_text.rfind('}') + 1
        ai_data = json.loads(ai_text[start:end])

        # שמירה ב-DB לשימוש עתידי
        db.save_prediction(game_id, home, away, ai_data)
        
        return ai_data
        
    except Exception as e:
        print(f"Prediction error: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate prediction")

if __name__ == "__main__":
    import uvicorn
    # הרצת השרת בפורט 8000
    uvicorn.run(app, host="0.0.0.0", port=8000)