export default function SuggestedQuestions({ questions, onSelect }) {
  if (!questions?.length) return null;

  return (
    <div className="suggested-questions">
      <p className="suggested-label">Try asking:</p>
      <div className="suggested-chips">
        {questions.map((q, i) => (
          <button
            key={i}
            className="suggested-chip"
            onClick={() => onSelect(q)}
          >
            {q}
          </button>
        ))}
      </div>
    </div>
  );
}
