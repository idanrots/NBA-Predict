import React, { useState, useEffect } from 'react';
import axios from 'axios';
// הוספתי את Sparkles לרשימת האייקונים
import { BrainCircuit, ArrowRight, ArrowLeft, Loader2, Trophy, Target, Sparkles } from 'lucide-react';
import './App.css';

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
    return `${year}-${month}-${day}`;
  };

  const formatDateForDisplay = (date) => {
    return new Intl.DateTimeFormat('en-US', { weekday: 'long', month: 'long', day: 'numeric' }).format(date);
  };

  const changeDate = (days) => {
    const newDate = new Date(selectedDate);
    newDate.setDate(selectedDate.getDate() + days);
    setSelectedDate(newDate);
  };

  const cleanTime = (timeStr) => {
    if (!timeStr) return "--:--";
    let clean = timeStr;
    if (timeStr.includes("-")) {
        clean = timeStr.split("-")[1];
    }
    return clean.replace("EST", "").replace("ET", "").trim();
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
      const payload = {
        game_id: gameId,
        date: formatDateForAPI(selectedDate),
        home_team: home,
        away_team: away
      };

      const res = await axios.post(`${API_URL}/predict`, payload);

      setPredictions(prev => ({ 
        ...prev, 
        [gameId]: {
          winner: res.data.predicted_winner,
          confidence: res.data.confidence,
          explanation: res.data.explanation,
          predHomeScore: res.data.pred_home_score,
          predAwayScore: res.data.pred_away_score
        } 
      }));

    } catch (err) {
      console.error("Prediction Error:", err);
      // הודעת שגיאה מותאמת למצב לוקאלי
      alert("Prediction request failed. Ensure backend is running on port 8000.");
    } finally {
      setPredictingId(null);
    }
  };

  return (
    <div className="app-container">
      
      {/* HEADER */}
      <header className="main-header">
        <div className="header-content">
          <div className="icon-wrapper">
            <Trophy size={55} strokeWidth={1.5} />
          </div>
          <div className="text-wrapper">
            <h1 className="neon-title">NBA AI PREDICTOR</h1>
            <p className="subtitle">SMART AI-BASED PREDICTION SYSTEM</p>
          </div>
        </div>
      </header>

      {/* DATE NAV */}
      <div className="date-nav-container">
        <div className="date-nav">
          <button onClick={() => changeDate(-1)} className="nav-btn">
            <ArrowLeft size={20} /> 
          </button>
          <div className="current-date">{formatDateForDisplay(selectedDate)}</div>
          <button onClick={() => changeDate(1)} className="nav-btn">
            <ArrowRight size={20} />
          </button>
        </div>
      </div>

      {/* GAMES LIST */}
      <div className="games-list">
        {loading ? (
          <div className="loading-state"><Loader2 className="animate-spin" size={40} color="#3b82f6" /></div>
        ) : games.length === 0 ? (
          <div className="empty-state">No games scheduled for this date 🏀</div>
        ) : (
          games.map((game) => (
            <div key={game.gameId} className="game-card">
              
              {/* Top Row: Teams & Action */}
              <div className="game-row-top">
                <div className="game-time">
                  <span className="time-val">{cleanTime(game.time).split(' ')[0]}</span>
                  <span className="time-ampm">{cleanTime(game.time).split(' ')[1] || 'PM'}</span>
                </div>

                <div className="teams-display">
                  <div className={`team-box home ${game.homeScore > game.awayScore ? 'winner' : ''}`}>
                    <img src={game.homeLogo} alt={game.homeTeam} className="team-logo" onError={(e) => {e.target.style.display='none'}}/>
                    <span className="team-name">{game.homeTeam}</span>
                  </div>

                  {/* Score Display */}
                  {game.status === 'Final' || (game.homeScore && game.awayScore) ? (
                    <div className="score-display">
                      <span className={`score-val ${game.homeScore > game.awayScore ? 'win-text' : ''}`}>
                        {game.homeScore}
                      </span>
                      <span className="score-divider">-</span>
                      <span className={`score-val ${game.awayScore > game.homeScore ? 'win-text' : ''}`}>
                        {game.awayScore}
                      </span>
                      {game.status === 'Final' && <span className="game-status">FINAL</span>}
                    </div>
                  ) : (
                    <div className="vs-badge">VS</div>
                  )}

                  <div className={`team-box away ${game.awayScore > game.homeScore ? 'winner' : ''}`}>
                    <img src={game.awayLogo} alt={game.awayTeam} className="team-logo" onError={(e) => {e.target.style.display='none'}}/>
                    <span className="team-name">{game.awayTeam}</span>
                  </div>
                </div>

                <div className="action-area">
                  {!predictions[game.gameId] ? (
                    <button 
                      onClick={() => handlePredict(game.gameId, game.homeTeam, game.awayTeam)}
                      disabled={predictingId === game.gameId}
                      className="predict-btn"
                    >
                      {predictingId === game.gameId ? <Loader2 size={16} className="animate-spin" /> : <BrainCircuit size={16} />}
                      <span>Analyze</span>
                    </button>
                  ) : (
                    <div className="prediction-badge">
                      <span className="pred-winner">{predictions[game.gameId].winner}</span>
                      <span className="pred-conf">{predictions[game.gameId].confidence}%</span>
                    </div>
                  )}
                </div>
              </div>

              {/* Bottom Row: AI Explanation + Predicted Score */}
              {predictions[game.gameId] && (
                <div className="prediction-explanation">
                  
                  {/* Predicted Score Box */}
                  <div className="predicted-score-container">
                    <div className="pred-label"><Target size={14}/> Predicted Score</div>
                    <div className="pred-score-vals">
                      <span className="p-team">{game.homeTeam}</span>
                      <span className="p-score">{predictions[game.gameId].predHomeScore}</span>
                      <span className="p-dash">-</span>
                      <span className="p-score">{predictions[game.gameId].predAwayScore}</span>
                      <span className="p-team">{game.awayTeam}</span>
                    </div>
                  </div>

                  {/* AI Reason - Beautiful Header */}
                  <div className="explanation-text">
                    <div className="explanation-header">
                      <Sparkles className="explanation-icon" size={18} />
                      <span className="explanation-title">AI PREDICTION REASON</span>
                    </div>
                    <p>{predictions[game.gameId].explanation}</p>
                  </div>
                </div>
              )}

            </div>
          ))
        )}
      </div>
    </div>
  );
}