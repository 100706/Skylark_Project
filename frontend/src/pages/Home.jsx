import { useState } from "react";
import ChatWindow from "../components/ChatWindow";
import Dashboard from "../components/Dashboard";

export default function Home() {
  const [latestMetrics, setLatestMetrics] = useState(null);
  const [latestIntent, setLatestIntent] = useState(null);
  const [showDashboard, setShowDashboard] = useState(false);

  const handleMetricsUpdate = (metrics, intent) => {
    setLatestMetrics(metrics);
    setLatestIntent(intent);
  };

  return (
    <div className="home-layout">
      {/* Sidebar toggle for mobile */}
      <button
        className="dashboard-toggle"
        onClick={() => setShowDashboard(!showDashboard)}
        aria-label="Toggle dashboard"
      >
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <rect x="3" y="3" width="7" height="7" />
          <rect x="14" y="3" width="7" height="7" />
          <rect x="3" y="14" width="7" height="7" />
          <rect x="14" y="14" width="7" height="7" />
        </svg>
      </button>

      {/* Chat Panel */}
      <div className="chat-panel">
        <ChatWindow onMetricsUpdate={handleMetricsUpdate} />
      </div>

      {/* Dashboard Panel */}
      <div className={`dashboard-panel ${showDashboard ? "show" : ""}`}>
        <Dashboard latestMetrics={latestMetrics} latestIntent={latestIntent} />
      </div>
    </div>
  );
}
