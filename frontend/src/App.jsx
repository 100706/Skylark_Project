import { useState } from "react";
import Home from "./pages/Home";
import Landing from "./pages/Landing";
import "./index.css";

function App() {
  const [currentView, setCurrentView] = useState("landing"); // 'landing' | 'app'

  if (currentView === "landing") {
    return <Landing onNavigate={setCurrentView} />;
  }

  return (
    <div className="app">
      <nav className="top-nav">
        <div className="nav-brand">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="nav-icon">
            <path d="M12 2L2 7l10 5 10-5-10-5z" />
            <path d="M2 17l10 5 10-5" />
            <path d="M2 12l10 5 10-5" />
          </svg>
          <span className="nav-title">Monday.com BI Agent</span>
        </div>
        <div className="nav-actions">
          <button className="logout-btn" onClick={() => setCurrentView("landing")}>
            Sign Out
          </button>
        </div>
      </nav>
      <main className="main-content">
        <Home />
      </main>
    </div>
  );
}

export default App;
