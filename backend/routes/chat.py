"""
Chat Route

POST /api/chat — Main conversation endpoint.
Orchestrates the full pipeline:
  Intent extraction → Data fetch → Clean → Compute → LLM explain
"""

import logging
import traceback

from flask import Blueprint, request, jsonify

from services.monday_client import fetch_work_orders, fetch_deals
from services.cleaner import clean_dataframe
from services.insights import compute_for_intent, leadership_summary
from services.llm import extract_intent, generate_explanation, generate_leadership_update, get_suggestions

logger = logging.getLogger(__name__)

chat_bp = Blueprint("chat", __name__)

# Cache cleaned DataFrames in memory to avoid re-fetching on every message.
# In production this would be Redis/memcached with TTL, but for a hackathon
# in-memory cache is fine — the data doesn't change during a demo.
_cache = {
    "deals_df": None,
    "wo_df": None,
    "deals_quality": None,
    "wo_quality": None,
}


def _ensure_data():
    """Fetch and clean data if not cached."""
    if _cache["deals_df"] is None or _cache["wo_df"] is None:
        logger.info("Fetching and cleaning data from Monday.com...")

        # Fetch from Monday.com API
        raw_deals = fetch_deals()
        raw_wo = fetch_work_orders()

        # Clean
        _cache["deals_df"], _cache["deals_quality"] = clean_dataframe(raw_deals, "deals")
        _cache["wo_df"], _cache["wo_quality"] = clean_dataframe(raw_wo, "work_orders")

        logger.info(
            f"Data loaded: {len(_cache['deals_df'])} deals, {len(_cache['wo_df'])} work orders"
        )


def _invalidate_cache():
    """Clear cached data to force re-fetch."""
    _cache["deals_df"] = None
    _cache["wo_df"] = None
    _cache["deals_quality"] = None
    _cache["wo_quality"] = None


@chat_bp.route("/chat", methods=["POST"])
def chat():
    """
    Main chat endpoint.
    
    Request:
        {
            "message": "What's our total revenue?",
            "conversation_history": [
                {"role": "user", "content": "..."},
                {"role": "assistant", "content": "..."}
            ]
        }
    
    Response:
        {
            "response": "Your total revenue is...",
            "metrics": {...},
            "data_quality": {...},
            "suggestions": [...],
            "intent": "revenue"
        }
    """
    try:
        body = request.get_json()
        if not body or "message" not in body:
            return jsonify({"error": "Missing 'message' field"}), 400

        user_message = body["message"].strip()
        conversation_history = body.get("conversation_history", [])

        if not user_message:
            return jsonify({"error": "Message cannot be empty"}), 400

        logger.info(f"Chat request: '{user_message[:100]}'")

        # Step 1: Extract intent
        intent = extract_intent(user_message)
        logger.info(f"Intent: {intent}")

        # Step 2: Check if clarification is needed
        if intent.get("needs_clarification") and intent.get("confidence", 1) < 0.5:
            return jsonify({
                "response": intent.get("clarification_question", "Could you be more specific about what you'd like to know?"),
                "metrics": None,
                "data_quality": None,
                "suggestions": get_suggestions(intent.get("intent_type", "summary")),
                "intent": intent.get("intent_type"),
                "needs_clarification": True,
            })

        # Step 3: Ensure data is loaded
        _ensure_data()

        # Step 4: Compute metrics
        intent_type = intent.get("intent_type", "summary")
        metrics = compute_for_intent(intent_type, _cache["deals_df"], _cache["wo_df"])

        if "error" in metrics:
            return jsonify({
                "response": f"I encountered an issue computing the metrics: {metrics['error']}",
                "metrics": None,
                "data_quality": None,
                "suggestions": get_suggestions("summary"),
                "intent": intent_type,
            })

        # Step 5: Combine quality reports
        data_quality = {
            "deals": _cache["deals_quality"],
            "work_orders": _cache["wo_quality"],
        }

        # Step 6: Generate LLM explanation
        explanation = generate_explanation(
            metrics=metrics,
            question=user_message,
            intent_type=intent_type,
            data_quality=data_quality,
            conversation_history=conversation_history,
        )

        # Step 7: Get follow-up suggestions
        suggestions = get_suggestions(intent_type)

        return jsonify({
            "response": explanation,
            "metrics": metrics,
            "data_quality": data_quality,
            "suggestions": suggestions,
            "intent": intent_type,
        })

    except ValueError as e:
        logger.error(f"Value error in chat: {e}")
        return jsonify({
            "error": str(e),
            "response": f"Configuration error: {str(e)}. Please check your Monday.com API token and board names.",
            "suggestions": [],
        }), 400

    except Exception as e:
        logger.exception(f"Unexpected error in chat: {e}")
        return jsonify({
            "error": "An unexpected error occurred",
            "response": "Sorry, I encountered an error processing your question. Please try again.",
            "detail": str(e),
            "suggestions": ["Give me a leadership summary", "What's our total revenue?"],
        }), 500


@chat_bp.route("/refresh", methods=["POST"])
def refresh_data():
    """Force re-fetch data from Monday.com."""
    try:
        _invalidate_cache()
        _ensure_data()
        return jsonify({
            "status": "refreshed",
            "deals_count": len(_cache["deals_df"]),
            "wo_count": len(_cache["wo_df"]),
            "deals_quality": _cache["deals_quality"],
            "wo_quality": _cache["wo_quality"],
        })
    except Exception as e:
        logger.exception(f"Error refreshing data: {e}")
        return jsonify({"error": str(e)}), 500
