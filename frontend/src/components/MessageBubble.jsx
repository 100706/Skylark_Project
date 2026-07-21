import ReactMarkdown from "react-markdown";
import MetricCard from "./MetricCard";

export default function MessageBubble({ message }) {
  const { role, content, metrics, isError, timestamp } = message;
  const isUser = role === "user";

  return (
    <div className={`message ${isUser ? "user" : "assistant"}`}>
      {!isUser && (
        <div className="message-avatar">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12 2L2 7l10 5 10-5-10-5z" />
            <path d="M2 17l10 5 10-5" />
            <path d="M2 12l10 5 10-5" />
          </svg>
        </div>
      )}
      <div className={`message-bubble ${isUser ? "user" : "assistant"} ${isError ? "error" : ""}`}>
        <div className="message-content">
          <ReactMarkdown>{content}</ReactMarkdown>
        </div>

        {/* Inline metric cards for key metrics */}
        {metrics?.metric_cards && (
          <div className="message-metrics">
            {metrics.metric_cards.slice(0, 4).map((card, i) => (
              <MetricCard
                key={i}
                title={card.title}
                value={card.value}
                trend={card.trend}
                trendDirection={card.trend_direction}
                compact
              />
            ))}
          </div>
        )}

        <span className="message-time">
          {timestamp
            ? new Date(timestamp).toLocaleTimeString([], {
                hour: "2-digit",
                minute: "2-digit",
              })
            : ""}
        </span>
      </div>
    </div>
  );
}
