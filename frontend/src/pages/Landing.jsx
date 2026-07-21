import React from "react";

export default function Landing({ onNavigate }) {
  return (
    <div className="landing-page">
      <div className="landing-content">
        <div className="brand-badge">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12 2L2 7l10 5 10-5-10-5z" />
            <path d="M2 17l10 5 10-5" />
            <path d="M2 12l10 5 10-5" />
          </svg>
          Monday.com BI Agent
        </div>
        <h1 className="landing-title">Your Data,<br />Democratized.</h1>
        <p className="landing-subtitle">
          Connect your Monday.com boards and chat directly with your pipeline, revenue, and work orders using natural language.
        </p>
        <div className="landing-actions">
          <button className="primary-btn" onClick={() => onNavigate("app")}>
            Open Dashboard
          </button>
        </div>
      </div>
      
      <div className="landing-visual">
        <div className="glass-card mockup-card">
          <div className="mockup-header">
            <div className="mockup-dots">
              <span></span><span></span><span></span>
            </div>
          </div>
          <div className="mockup-body">
            <div className="mockup-bubble user">What's our weighted pipeline?</div>
            <div className="mockup-bubble agent">Your weighted pipeline value is ₹27.31 Cr across 49 open deals.</div>
          </div>
        </div>
      </div>
    </div>
  );
}
