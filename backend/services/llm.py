"""
LLM Service (Gemini Integration)

Handles all LLM interactions:
- Intent extraction from natural language questions
- Generating explanations for computed metrics
- Generating leadership updates

The LLM NEVER computes business metrics — it only narrates/explains
pre-computed results from insights.py.

Uses google-generativeai (legacy SDK) for lighter dependency footprint.
"""

import os
import json
import logging
from pathlib import Path

import google.generativeai as genai

logger = logging.getLogger(__name__)

# Load system prompt
_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
_SYSTEM_PROMPT = (_PROMPTS_DIR / "system_prompt.txt").read_text(encoding="utf-8")

# Initialize Gemini
_model = None


def _get_model():
    """Lazy-initialize Gemini model."""
    global _model
    if _model is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set")
        genai.configure(api_key=api_key)
        _model = genai.GenerativeModel(
            model_name="gemini-2.0-flash",
            system_instruction=_SYSTEM_PROMPT,
        )
    return _model


# ---------------------------------------------------------------------------
# Intent Extraction
# ---------------------------------------------------------------------------

_INTENT_PROMPT = """You are an intent classifier for a Business Intelligence system. 
Analyze the user's question and extract structured intent.

Available intent types:
- "revenue" — questions about total revenue, revenue figures
- "revenue_by_sector" — revenue breakdown by sector/industry
- "pipeline" — pipeline value, open deals, deal stages
- "conversion" — conversion rates, win rates
- "deal_size" — average or median deal sizes
- "deals_by_sector" — deal distribution by sector
- "delayed" — delayed, stuck, or overdue work orders
- "wo_status" — work order status breakdown
- "wo_by_sector" — work orders by sector
- "billing" — billing, collections, receivables
- "top_clients" — top clients, biggest accounts
- "cross_board" — cross-board analysis (deals vs work orders overlap)
- "summary" — leadership update, executive summary, overall health

Respond ONLY with a JSON object (no markdown, no code fences):
{
    "intent_type": "one of the types above",
    "needs_clarification": true/false,
    "clarification_question": "question to ask if ambiguous (or null)",
    "filters": {
        "sector": "sector name if mentioned (or null)",
        "time_period": "time period if mentioned (or null)",
        "client": "client name if mentioned (or null)",
        "status": "status filter if mentioned (or null)"
    },
    "confidence": 0.0 to 1.0
}

If the question is ambiguous or could map to multiple intents, set needs_clarification to true and provide a clarification_question.

User question: """


def extract_intent(user_message: str) -> dict:
    """
    Extract structured intent from a user's natural language question.
    
    Returns:
        {
            "intent_type": str,
            "needs_clarification": bool,
            "clarification_question": str | None,
            "filters": dict,
            "confidence": float
        }
    """
    try:
        model = _get_model()
        response = model.generate_content(_INTENT_PROMPT + user_message)

        # Parse JSON response
        text = response.text.strip()
        # Remove markdown code fences if present
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            text = text.rsplit("```", 1)[0]
        
        intent = json.loads(text)
        logger.info(f"Extracted intent: {intent.get('intent_type')} (confidence: {intent.get('confidence')})")
        return intent

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse intent JSON: {e}")
        return _keyword_fallback(user_message)
    except Exception as e:
        logger.error(f"Intent extraction failed: {e}")
        return _keyword_fallback(user_message)


def _keyword_fallback(message: str) -> dict:
    """Simple keyword-based intent detection as fallback."""
    message_lower = message.lower()

    keyword_map = {
        "revenue_by_sector": ["revenue by sector", "sector revenue", "sector wise", "revenue breakdown"],
        "deals_by_sector": ["deals by sector", "sector deal"],
        "wo_by_sector": ["work order by sector", "sector work order"],
        "cross_board": ["cross board", "overlap", "deal and work order"],
        "top_clients": ["top client", "biggest client", "best client", "key account"],
        "deal_size": ["deal size", "average deal", "typical deal"],
        "wo_status": ["work order status", "wo status", "project status"],
        "revenue": ["revenue", "earned", "income", "sales figure"],
        "pipeline": ["pipeline", "open deal", "funnel", "prospect"],
        "conversion": ["conversion", "win rate", "close rate"],
        "delayed": ["delay", "stuck", "overdue", "late", "behind"],
        "billing": ["bill", "invoice", "collect", "receivable", "payment"],
        "summary": ["summary", "overview", "update", "health", "leadership", "executive"],
    }

    for intent_type, keywords in keyword_map.items():
        if any(kw in message_lower for kw in keywords):
            return {
                "intent_type": intent_type,
                "needs_clarification": False,
                "clarification_question": None,
                "filters": {},
                "confidence": 0.6,
            }

    return {
        "intent_type": "summary",
        "needs_clarification": False,
        "clarification_question": None,
        "filters": {},
        "confidence": 0.3,
    }


# ---------------------------------------------------------------------------
# Explanation Generation
# ---------------------------------------------------------------------------

def generate_explanation(
    metrics: dict,
    question: str,
    intent_type: str,
    data_quality: dict = None,
    conversation_history: list = None,
) -> str:
    """
    Generate a natural language explanation for computed metrics.
    
    The LLM receives pre-computed metrics and ONLY explains them.
    It must not invent, recalculate, or adjust any numbers.
    """
    # Build context for the LLM
    context_parts = [
        f"User's question: {question}",
        f"Intent: {intent_type}",
        f"Computed metrics (use these numbers EXACTLY, do not recalculate):\n{json.dumps(metrics, indent=2, default=str)}",
    ]

    if data_quality:
        context_parts.append(
            f"Data quality notes: {json.dumps(data_quality, indent=2, default=str)}"
        )

    context = "\n\n".join(context_parts)

    # Build chat history for multi-turn context
    history = []
    if conversation_history:
        for msg in conversation_history[-6:]:  # Last 3 exchanges
            role = "user" if msg.get("role") == "user" else "model"
            history.append({"role": role, "parts": [msg.get("content", "")]})

    try:
        model = _get_model()
        chat = model.start_chat(history=history)
        response = chat.send_message(context)
        return response.text.strip()
    except Exception as e:
        logger.error(f"Explanation generation failed: {e}")
        return _fallback_explanation(metrics, intent_type)


def _fallback_explanation(metrics: dict, intent_type: str) -> str:
    """Generate a basic explanation without the LLM."""
    parts = [f"Here are the {intent_type.replace('_', ' ')} metrics:\n"]
    for key, value in metrics.items():
        if key.endswith("_formatted") or key == "metric_cards":
            continue
        
        label = key.replace("_", " ").title()
        formatted_key = f"{key}_formatted"
        
        if formatted_key in metrics:
            parts.append(f"• **{label}**: {metrics[formatted_key]}")
        elif isinstance(value, list) and len(value) > 0 and isinstance(value[0], dict):
            parts.append(f"\n**Breakdown ({label}):**")
            for item in value[:15]:
                item_parts = []
                for k, v in item.items():
                    if k.endswith("_formatted") or k == "id": continue
                    if f"{k}_formatted" in item:
                        item_parts.append(f"{str(k).title()}: {item[f'{k}_formatted']}")
                    else:
                        item_parts.append(f"{str(k).title()}: {v}")
                parts.append(" - " + ", ".join(item_parts))
        elif isinstance(value, list):
            if value:
                parts.append(f"• **{label}**: {', '.join(str(v) for v in value)}")
        elif isinstance(value, (int, float, str)) and not isinstance(value, bool):
            parts.append(f"• **{label}**: {value}")
            
    return "\n".join(parts) if len(parts) > 1 else "I've computed the metrics, but couldn't generate a detailed explanation right now."


# ---------------------------------------------------------------------------
# Leadership Update Generation
# ---------------------------------------------------------------------------

def generate_leadership_update(summary_data: dict) -> str:
    """
    Generate a formatted leadership/executive update from summary metrics.
    """
    context = f"""Generate a leadership update based on these metrics. 
Format it as a professional executive briefing.

Metrics:
{json.dumps(summary_data, indent=2, default=str)}

Format the update with:
1. Key headline numbers (Revenue, Pipeline, Delayed, Top Sector)
2. Notable observations
3. 2-3 actionable recommendations
4. Any data quality caveats from the quality report
"""

    try:
        model = _get_model()
        response = model.generate_content(context)
        return response.text.strip()
    except Exception as e:
        logger.error(f"Leadership update generation failed: {e}")
        return "Leadership update could not be generated at this time."


# ---------------------------------------------------------------------------
# Suggested Follow-up Questions
# ---------------------------------------------------------------------------

_SUGGESTIONS_BY_INTENT = {
    "revenue": [
        "How does revenue break down by sector?",
        "What's our average deal size?",
        "Show me the conversion rate",
    ],
    "pipeline": [
        "What's the weighted pipeline value?",
        "Which deals are in the negotiation stage?",
        "Show revenue by sector",
    ],
    "delayed": [
        "What's the billing summary?",
        "Show work orders by status",
        "Which sectors have the most delays?",
    ],
    "summary": [
        "Show me delayed work orders",
        "What's the pipeline breakdown by stage?",
        "Who are our top clients?",
    ],
    "billing": [
        "What are our total receivables?",
        "Show delayed work orders",
        "What's the collection rate?",
    ],
}

_DEFAULT_SUGGESTIONS = [
    "Give me a leadership summary",
    "What's our total revenue?",
    "Show me delayed work orders",
    "What does our pipeline look like?",
]


def get_suggestions(intent_type: str) -> list[str]:
    """Get suggested follow-up questions based on the current intent."""
    return _SUGGESTIONS_BY_INTENT.get(intent_type, _DEFAULT_SUGGESTIONS)
