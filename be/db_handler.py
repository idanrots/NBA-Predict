import psycopg2
import os
import json

class DBHandler:
    def __init__(self):
        # שימוש בכתובת ה-RDS שסיפקת
        self.host = os.getenv("DB_HOST", "database-1.cmtkkqyiagdy.us-east-1.rds.amazonaws.com")
        self.dbname = os.getenv("DB_NAME", "postgres")
        self.user = os.getenv("DB_USER", "postgres")
        self.password = os.getenv("DB_PASSWORD", "your_password")

    def get_connection(self):
        """יוצר חיבור למסד הנתונים ב-AWS RDS"""
        return psycopg2.connect(
            host=self.host,
            database=self.dbname,
            user=self.user,
            password=self.password
        )

    def get_prediction(self, game_id):
        """בודק אם כבר קיים חיזוי ב-DB כדי לחסוך פנייה ל-AI"""
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT prediction_json FROM game_predictions WHERE game_id = %s", (game_id,))
                result = cur.fetchone()
                return json.loads(result[0]) if result else None
        finally:
            conn.close()

    def save_prediction(self, game_id, home, away, prediction_json):
        """שומר את החיזוי החדש ב-DB לשימוש עתידי"""
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO game_predictions (game_id, home_team, away_team, prediction_json) VALUES (%s, %s, %s, %s) ON CONFLICT (game_id) DO NOTHING",
                    (game_id, home, away, json.dumps(prediction_json))
                )
                conn.commit()
        finally:
            conn.close()