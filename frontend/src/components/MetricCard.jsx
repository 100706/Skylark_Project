export default function MetricCard({ title, value, trend, trendDirection, compact }) {
  const getTrendClass = () => {
    if (!trendDirection) return "";
    return trendDirection === "up" ? "trend-up" : trendDirection === "down" ? "trend-down" : "trend-neutral";
  };

  return (
    <div className={`metric-card ${compact ? "compact" : ""}`}>
      <div className="metric-title">{title}</div>
      <div className="metric-value">{value}</div>
      {trend && (
        <div className={`metric-trend ${getTrendClass()}`}>
          {trendDirection === "up" && "↑ "}
          {trendDirection === "down" && "↓ "}
          {trend}
        </div>
      )}
    </div>
  );
}
