import { useState, useEffect } from "react";
import MetricCard from "./MetricCard";
import { getSummary } from "../api/api";

export default function Dashboard({ latestMetrics, latestIntent }) {
  const [summary, setSummary] = useState(null);
  const [dataQuality, setDataQuality] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Load summary on first render
  useEffect(() => {
    loadSummary();
  }, []);

  const loadSummary = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getSummary();
      setSummary(data.summary);
      setDataQuality(data.data_quality);
    } catch (err) {
      setError("Could not load dashboard. Make sure the backend is running.");
    } finally {
      setLoading(false);
    }
  };

  // Determine which cards to show
  const cards = summary?.metric_cards || latestMetrics?.metric_cards || [];

  if (loading) {
    return (
      <div className="dashboard">
        <div className="dashboard-header">
          <h2>Leadership Dashboard</h2>
        </div>
        <div className="dashboard-loading">
          <div className="spinner"></div>
          <p>Loading metrics from Monday.com...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="dashboard">
        <div className="dashboard-header">
          <h2>Leadership Dashboard</h2>
        </div>
        <div className="dashboard-error">
          <p>{error}</p>
          <button onClick={loadSummary} className="retry-btn">Retry</button>
        </div>
      </div>
    );
  }

  return (
    <div className="dashboard">
      <div className="dashboard-header">
        <h2>Leadership Dashboard</h2>
        <button onClick={loadSummary} className="refresh-btn" title="Refresh data">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <polyline points="23 4 23 10 17 10" />
            <polyline points="1 20 1 14 7 14" />
            <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
          </svg>
        </button>
      </div>

      <div className="dashboard-grid">
        {cards.map((card, i) => (
          <MetricCard
            key={i}
            title={card.title}
            value={card.value}
            trend={card.trend}
            trendDirection={card.trend_direction}
          />
        ))}
      </div>

      {/* Sector breakdown */}
      {summary?.sector_breakdown?.sectors?.length > 0 && (
        <div className="dashboard-section">
          <h3>Revenue by Sector</h3>
          <div className="sector-bars">
            {summary.sector_breakdown.sectors.map((s, i) => (
              <div key={i} className="sector-bar-row">
                <span className="sector-name">{s.sector}</span>
                <div className="sector-bar-track">
                  <div
                    className="sector-bar-fill"
                    style={{ width: `${s.share_percentage}%` }}
                  />
                </div>
                <span className="sector-value">{s.revenue_formatted}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Work order status */}
      {summary?.work_order_status?.statuses?.length > 0 && (
        <div className="dashboard-section">
          <h3>Work Orders by Status</h3>
          <div className="status-chips">
            {summary.work_order_status.statuses.map((s, i) => (
              <div key={i} className="status-chip">
                <span className="status-chip-count">{s.count}</span>
                <span className="status-chip-label">{s.status}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Data Quality */}
      {dataQuality && (
        <div className="dashboard-section quality-section">
          <h3>Data Quality (Cleaning Report)</h3>
          <div className="quality-indicators">
            <div className="quality-badge">
              <span className="quality-score">
                {dataQuality?.deals?.score || "—"}%
              </span>
              <span className="quality-label">Deals Health</span>
            </div>
            <div className="quality-badge">
              <span className="quality-score">
                {dataQuality?.work_orders?.score || "—"}%
              </span>
              <span className="quality-label">Work Orders Health</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
