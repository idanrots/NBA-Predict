import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { 
  BrainCircuit, 
  ArrowRight, // אייקון חץ ימינה
  ArrowLeft,  // אייקון חץ שמאלה
  Loader2 
} from 'lucide-react';
import './App.css';

// const API_URL = process.env.REACT_APP_API_URL || "http://127.0.0.1:8000";
const API_URL = "http://127.0.0.1:8000";

export default function NBAPredictor() {
  const [games, setGames] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedDate, setSelectedDate] = useState(new Date());
  const [predictions, setPredictions] = useState({});
  const [predictingId, setPredictingId] = useState(null);

  const formatDateForAPI = (date) => {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}${month}${day}`;
  };

  const formatDateForDisplay = (date) => {
    return new Intl.DateTimeFormat('he-IL', { weekday: 'long', day: 'numeric', month: 'long' }).format(date);
  };

  const changeDate = (days) => {
    const newDate = new Date(selectedDate);
    newDate.setDate(selectedDate.getDate() + days);
    setSelectedDate(newDate);
  };

  useEffect(() => {
    const fetchGames = async () => {
      setLoading(true);
      const dateStr = formatDateForAPI(selectedDate);
      try {
        const res = await axios.get(`${API_URL}/games?date=${dateStr}`);
        setGames(Array.isArray(res.data) ? res.data : []);
      } catch (err) {
        console.error("Error fetching games:", err);
      } finally {
        setLoading(false);
      }
    };
    fetchGames();
  }, [selectedDate]);

  const handlePredict = async (gameId, home, away) => {
    if (predictions[gameId]) return;
    setPredictingId(gameId);
    try {
      const res = await axios.get(`${API_URL}/predict/${gameId}?home=${home}&away=${away}`);
      setPredictions(prev => ({ ...prev, [gameId]: res.data }));
    } catch (err) {
      alert("שגיאה בחיזוי");
    } finally {
      setPredictingId(null);
    }
  };

  // --- פונקציה חדשה לניקוי השעה ---
  // הופכת "1/8 - 7:00 PM EST" ל-"7:00 PM"
  const cleanTime = (timeStr) => {
    if (!timeStr) return "--:--";
    
    // אם יש מקף (כמו בתאריך), נחתוך את כל מה שלפניו
    if (timeStr.includes("-")) {
      const parts = timeStr.split("-");
      // לוקחים את החלק השני ומנקים רווחים ו-EST
      let timeOnly = parts[1].trim(); 
      return timeOnly.replace("EST", "").replace("ET", "").trim();
    }
    
    // אם אין מקף, רק נוריד את אזור הזמן
    return timeStr.replace("EST", "").replace("ET", "").trim();
  };

  return (
    <div className="app-container">
      
      <header className="main-header">
        <h1>NBA AI Predictor</h1>
      </header>

      <div className="date-nav-container">
        <div className="date-nav">
          {/* כפתור אחורה עם חץ */}
          <button onClick={() => changeDate(-1)} className="nav-btn">
            <ArrowRight size={20} /> 
          </button>
          
          <div className="current-date">
            {formatDateForDisplay(selectedDate)}
          </div>
          
          {/* כפתור קדימה עם חץ */}
          <button onClick={() => changeDate(1)} className="nav-btn">
            <ArrowLeft size={20} />
          </button>
        </div>
      </div>

      <div className="games-list">
        {loading ? (
          <div style={{textAlign: 'center', marginTop: '50px'}}>
            <Loader2 className="animate-spin" size={40} color="#a855f7" />
          </div>
        ) : games.length === 0 ? (
          <div style={{textAlign: 'center', color: '#71717a'}}>אין משחקים בתאריך זה 🏀</div>
        ) : (
          games.map((game) => (
            <div key={game.gameId} className="game-card">
              
              {/* צד שמאל: שעה נקייה */}
              <div className="game-time">
                {cleanTime(game.time)}
              </div>

              {/* אמצע: קבוצות */}
              <div className="teams-display">
                <div className="team-box home">
                  <span className="team-name">{game.homeTeam}</span>
                </div>

                <div className="vs-badge">VS</div>

                <div className="team-box away">
                  <span className="team-name">{game.awayTeam}</span>
                </div>
              </div>

              {/* צד ימין: כפתור */}
              <div className="action-area">
                {!predictions[game.gameId] ? (
                  <button 
                    onClick={() => handlePredict(game.gameId, game.homeTeam, game.awayTeam)}
                    disabled={predictingId === game.gameId}
                    className="predict-btn"
                  >
                    {predictingId === game.gameId ? (
                      <Loader2 size={16} className="animate-spin" />
                    ) : (
                      <BrainCircuit size={16} />
                    )}
                    <span>AI Analyze</span>
                  </button>
                ) : (
                  <div className="prediction-badge">
                    <span className="pred-winner">{predictions[game.gameId].winner}</span>
                    <span className="pred-conf">{predictions[game.gameId].confidence}%</span>
                  </div>
                )}
              </div>

            </div>
          ))
        )}
      </div>
    </div>
  );
}