const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:5000/api";

/**
 * Send a chat message to the backend.
 * @param {string} message - User's natural language question
 * @param {Array} conversationHistory - Previous messages for context
 * @returns {Promise<Object>} Response with explanation, metrics, suggestions
 */
export async function sendMessage(message, conversationHistory = []) {
  const response = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message,
      conversation_history: conversationHistory,
    }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.response || error.error || "Failed to send message");
  }

  return response.json();
}

/**
 * Get list of accessible Monday.com boards.
 */
export async function getBoards() {
  const response = await fetch(`${API_BASE}/monday/boards`);
  if (!response.ok) throw new Error("Failed to fetch boards");
  return response.json();
}

/**
 * Get leadership summary with all KPIs.
 */
export async function getSummary() {
  const response = await fetch(`${API_BASE}/monday/summary`);
  if (!response.ok) throw new Error("Failed to fetch summary");
  return response.json();
}

/**
 * Check backend health.
 */
export async function checkHealth() {
  const response = await fetch(`${API_BASE}/health`);
  if (!response.ok) throw new Error("Backend unreachable");
  return response.json();
}

/**
 * Check Monday.com API connectivity.
 */
export async function checkMondayHealth() {
  const response = await fetch(`${API_BASE}/monday/health`);
  if (!response.ok) throw new Error("Monday.com API unreachable");
  return response.json();
}

/**
 * Force refresh data from Monday.com.
 */
export async function refreshData() {
  const response = await fetch(`${API_BASE}/refresh`, { method: "POST" });
  if (!response.ok) throw new Error("Failed to refresh data");
  return response.json();
}
