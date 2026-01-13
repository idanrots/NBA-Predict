import psycopg2
import json

class DBHandler:
    def __init__(self):
        # פרטי התחברות Hard Coded
        self.host = "database-1.cwhs6wyesi0g.us-east-1.rds.amazonaws.com"
        self.dbname = "postgres"
        self.user = "postgres"
        self.password = "Idan1107!"
        self.port = "5432"

        # יצירת הטבלה באופן אוטומטי אם היא לא קיימת
        self._create_table_if_not_exists()

    def get_connection(self):
        """יוצר חיבור למסד הנתונים ב-AWS RDS"""
        try:
            return psycopg2.connect(
                host=self.host,
                database=self.dbname,
                user=self.user,
                password=self.password,
                port=self.port
            )
        except Exception as e:
            print(f"Error connecting to DB: {e}")
            raise e

    def _create_table_if_not_exists(self):
        """פונקציית עזר ליצירת הטבלה אם היא חסרה"""
        create_table_query = """
        CREATE TABLE IF NOT EXISTS game_predictions (
            game_id VARCHAR(50) PRIMARY KEY,
            home_team VARCHAR(50),
            away_team VARCHAR(50),
            prediction_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(create_table_query)
                conn.commit()
        except Exception as e:
            print(f"Error creating table: {e}")
        finally:
            conn.close()

    def get_prediction(self, game_id):
        """בודק אם כבר קיים חיזוי ב-DB"""
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT prediction_json FROM game_predictions WHERE game_id = %s", (game_id,))
                result = cur.fetchone()
                return json.loads(result[0]) if result else None
        finally:
            conn.close()

    def save_prediction(self, game_id, home, away, prediction_json):
        """שומר את החיזוי החדש ב-DB"""
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO game_predictions (game_id, home_team, away_team, prediction_json) 
                    VALUES (%s, %s, %s, %s) 
                    ON CONFLICT (game_id) DO UPDATE 
                    SET prediction_json = EXCLUDED.prediction_json
                    """,
                    (game_id, home, away, json.dumps(prediction_json))
                )
                conn.commit()
        except Exception as e:
            print(f"Error saving prediction: {e}")
        finally:
            conn.close()

    def fetch_all_predictions(self):
        """מחזיר את כל התחזיות השמורות כרשימה של מילונים"""
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                # שימוש בשם הטבלה הנכון: game_predictions
                cur.execute("SELECT prediction_json FROM game_predictions")
                rows = cur.fetchall()
                
                results = []
                for row in rows:
                    if row and row[0]:
                        # במקרה של Postgres הנתונים חוזרים לפעמים כבר כ-dict או כמחרוזת
                        # תלוי בדרייבר, כאן נניח שזה טקסט (בגלל הגדרת העמודה כ-TEXT)
                        try:
                            data = json.loads(row[0])
                            results.append(data)
                        except TypeError:
                            # אם הדרייבר כבר המיר ל-dict באופן אוטומטי
                            results.append(row[0])
                            
                return results
        except Exception as e:
            print(f"Error fetching all predictions: {e}")
            return []
        finally:
            conn.close()