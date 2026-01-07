import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Trophy, Activity, Loader2, Sparkles, ChevronRight, ChevronLeft, Calendar } from 'lucide-react';
import './App.css';

const API_URL = process.env.REACT_APP_API_URL || "http://127.0.0.1:8000";

export default function NBAPredictor() {
  const [games, setGames] = useState([]);
  const [loadingGameId, setLoadingGameId] = useState(null);
  const [predictions, setPredictions] = useState({});
  
  // ניהול תאריך - מתחילים מהיום
  const [selectedDate, setSelectedDate] = useState(new Date());

  // פונקציה שמפרמטת תאריך ל-API (YYYY-MM-DD)
  const formatDateForAPI = (date) => {
    return date.toISOString().split('T')[0];
  };

  // פונקציה לתצוגה יפה בעברית
  const formatDateForDisplay = (date) => {
    return new Intl.DateTimeFormat('he-IL', { weekday: 'long', day: 'numeric', month: 'long' }).format(date);
  };

  // בדיקה האם התאריך הנבחר הוא היום (כדי לחסום חזרה אחורה)
  const isToday = (date) => {
    const today = new Date();
    return date.getDate() === today.getDate() &&
           date.getMonth() === today.getMonth() &&
           date.getFullYear() === today.getFullYear();
  };

  useEffect(() => {
    // שליפת משחקים בכל פעם שהתאריך משתנה
    const dateStr = formatDateForAPI(selectedDate);
    setGames([]); // איפוס רשימה בזמן טעינה
    
    axios.get(`${API_URL}/games?date=${dateStr}`)
      .then(res => setGames(res.data))
      .catch(err => console.error("Error fetching games:", err));
  }, [selectedDate]);

  // שינוי תאריך
  const changeDate = (days) => {
    const newDate = new Date(selectedDate);
    newDate.setDate(selectedDate.getDate() + days);
    
    // מניעת חזרה לעבר (לפני היום)
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    if (days < 0 && newDate < today) return;

    setSelectedDate(newDate);
  };

  const handlePredict = async (gameId, home, away) => {
    if (predictions[gameId]) return;

    setLoadingGameId(gameId);
    try {
      const res = await axios.get(`${API_URL}/predict/${gameId}?home=${home}&away=${away}`);
      setPredictions(prev => ({ ...prev, [gameId]: res.data }));
    } catch (err) {
      alert("שגיאה בקבלת חיזוי");
    } finally {
      setLoadingGameId(null);
    }
  };

  return (
    <div className="nba-container">
      <h1 className="app-header">
        <Activity color="#ec4899" size={36} /> 
        NBA AI Predictor
      </h1>

      {/* בר ניווט תאריכים */}
      <div className="date-navigation">
        <button 
          className="nav-btn" 
          onClick={() => changeDate(-1)}
          disabled={isToday(selectedDate)} // חוסם אם זה היום
          style={{ opacity: isToday(selectedDate) ? 0.3 : 1 }}
        >
          <ChevronRight size={24} /> {/* חץ ימינה בממשק עברי זה "אחורה" */}
        </button>

        <div className="current-date-display">
          <Calendar size={20} className="calendar-icon" />
          <span>{formatDateForDisplay(selectedDate)}</span>
        </div>

        <button className="nav-btn" onClick={() => changeDate(1)}>
          <ChevronLeft size={24} /> {/* חץ שמאלה בממשק עברי זה "קדימה" */}
        </button>
      </div>
      
      {/* אזור המשחקים */}
      <div className="games-grid">
        {games.length === 0 ? (
          <div className="empty-state">אין משחקים מתוכננים לתאריך זה 🏀</div>
        ) : (
          games.map(game => (
            <div key={game.gameId} className="game-card">
              <div className="game-header">
                <span className="team-name">{game.homeTeam} 🏠</span>
                <span className="game-time">{game.time}</span>
                <span className="team-name">🏀 {game.awayTeam}</span>
              </div>

              {!predictions[game.gameId] ? (
                <button 
                  className="predict-btn"
                  onClick={() => handlePredict(game.gameId, game.homeTeam, game.awayTeam)}
                  disabled={loadingGameId === game.gameId}
                >
                  {loadingGameId === game.gameId ? (
                    <>
                      <Loader2 className="animate-spin" size={20} /> מנתח...
                    </>
                  ) : (
                    <>
                      <Sparkles size={20} /> חזה מנצחת (AI)
                    </>
                  )}
                </button>
              ) : (
                <div className="prediction-box">
                  <div className="prediction-header">
                    <span className="winner-text">
                      <Trophy size={18} style={{display:'inline', marginRight:'5px'}} />
                      {predictions[game.gameId].winner}
                    </span>
                    <span className="confidence-badge">
                      {predictions[game.gameId].confidence}%
                    </span>
                  </div>
                  <p className="reasoning-text">
                    {predictions[game.gameId].reasoning}
                  </p>
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}