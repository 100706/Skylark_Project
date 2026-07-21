import { useState, useRef, useEffect } from "react";
import ChatInput from "./ChatInput";
import MessageBubble from "./MessageBubble";
import SuggestedQuestions from "./SuggestedQuestions";
import { sendMessage } from "../api/api";

const INITIAL_SUGGESTIONS = [
  "Give me a leadership summary",
  "What's our total revenue?",
  "Show me delayed work orders",
  "What does our deal pipeline look like?",
  "Who are our top clients?",
  "Show revenue breakdown by sector",
];

export default function ChatWindow({ onMetricsUpdate }) {
  const [messages, setMessages] = useState(() => {
    const saved = localStorage.getItem("skylark_chat");
    if (saved) {
      try {
        return JSON.parse(saved);
      } catch (e) {}
    }
    return [
      {
        role: "assistant",
        content:
          "👋 Hi! I'm your Business Intelligence Agent. I can analyze your Monday data across **Work Orders** and **Deals** boards.\n\nAsk me anything about revenue, pipeline, delayed projects, billing, or request a full leadership summary.",
        timestamp: new Date(),
      },
    ];
  });

  useEffect(() => {
    localStorage.setItem("skylark_chat", JSON.stringify(messages));
  }, [messages]);
  const [isLoading, setIsLoading] = useState(false);
  const [suggestions, setSuggestions] = useState(INITIAL_SUGGESTIONS);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = async (text) => {
    if (!text.trim() || isLoading) return;

    // Add user message
    const userMessage = {
      role: "user",
      content: text,
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);

    try {
      // Build conversation history for context
      const history = messages.map((m) => ({
        role: m.role,
        content: m.content,
      }));

      const data = await sendMessage(text, history);

      // Add assistant response
      const assistantMessage = {
        role: "assistant",
        content: data.response,
        metrics: data.metrics,
        dataQuality: data.data_quality,
        intent: data.intent,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, assistantMessage]);

      // Update suggestions
      if (data.suggestions?.length) {
        setSuggestions(data.suggestions);
      }

      // Notify parent of metrics for dashboard
      if (data.metrics && onMetricsUpdate) {
        onMetricsUpdate(data.metrics, data.intent);
      }
    } catch (error) {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: `⚠️ ${error.message || "Something went wrong. Please try again."}`,
          isError: true,
          timestamp: new Date(),
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="chat-window">
      <div className="chat-header">
        <div className="chat-header-icon">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
          </svg>
        </div>
        <div>
          <h2>BI Agent</h2>
          <span className="chat-header-status">
            <span className="status-dot"></span>
            Connected to Monday.com
          </span>
        </div>
      </div>

      <div className="chat-messages">
        {messages.map((msg, i) => (
          <MessageBubble key={i} message={msg} />
        ))}

        {isLoading && (
          <div className="message assistant">
            <div className="message-bubble assistant">
              <div className="typing-indicator">
                <span></span>
                <span></span>
                <span></span>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {!isLoading && messages.length <= 2 && (
        <SuggestedQuestions
          questions={suggestions}
          onSelect={handleSend}
        />
      )}

      <ChatInput onSend={handleSend} disabled={isLoading} />
    </div>
  );
}
