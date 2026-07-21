"""
Monday.com Routes

Diagnostic and data inspection endpoints:
- GET /api/monday/health — Test Monday.com API connectivity
- GET /api/monday/boards — List all accessible boards
- GET /api/monday/preview/<board_key> — Preview first rows of a board
- GET /api/monday/summary — Leadership summary (requires data fetch + clean + compute)
"""

import logging
from flask import Blueprint, jsonify

from services.monday_client import (
    list_boards,
    find_board_by_name,
    fetch_board_items,
    fetch_board_schema,
    items_to_dataframe,
    fetch_work_orders,
    fetch_deals,
)

logger = logging.getLogger(__name__)

monday_bp = Blueprint("monday", __name__)


@monday_bp.route("/health", methods=["GET"])
def monday_health():
    """Test Monday.com API connectivity."""
    try:
        boards = list_boards(limit=1)
        return jsonify({
            "status": "connected",
            "accessible_boards": len(boards),
            "sample_board": boards[0] if boards else None,
        })
    except ValueError as e:
        return jsonify({"status": "error", "detail": str(e)}), 401
    except Exception as e:
        return jsonify({"status": "error", "detail": str(e)}), 500


@monday_bp.route("/boards", methods=["GET"])
def get_boards():
    """List all accessible boards."""
    try:
        boards = list_boards()
        return jsonify({"boards": boards, "count": len(boards)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@monday_bp.route("/preview/<board_key>", methods=["GET"])
def preview_board(board_key: str):
    """
    Preview schema and first 5 rows of a board.
    board_key: "work_orders" or "deals"
    """
    try:
        board_map = {
            "work_orders": ("Work Orders", "WORK_ORDERS_BOARD_ID"),
            "deals": ("Deals", "DEALS_BOARD_ID"),
        }

        if board_key not in board_map:
            return jsonify({"error": f"Unknown board key: {board_key}. Use 'work_orders' or 'deals'"}), 400

        board_name, env_key = board_map[board_key]
        board = find_board_by_name(board_name, env_override_key=env_key)

        if not board:
            return jsonify({"error": f"Board '{board_name}' not found"}), 404

        # Fetch schema
        schema = fetch_board_schema(board["id"])

        # Fetch items (limit to 5 for preview)
        items, _ = fetch_board_items(board["id"], limit=5)
        df = items_to_dataframe(items[:5])

        return jsonify({
            "board": board,
            "schema": schema,
            "sample_rows": df.to_dict(orient="records") if not df.empty else [],
            "column_count": len(schema),
            "sample_row_count": len(df),
        })

    except Exception as e:
        logger.exception(f"Error previewing board {board_key}: {e}")
        return jsonify({"error": str(e)}), 500


@monday_bp.route("/summary", methods=["GET"])
def get_summary():
    """
    Fetch both boards, clean, and return leadership summary metrics.
    This is a heavier endpoint — it does the full fetch+clean+compute pipeline.
    """
    try:
        from services.cleaner import clean_dataframe
        from services.insights import leadership_summary

        raw_deals = fetch_deals()
        raw_wo = fetch_work_orders()

        deals_df, deals_quality = clean_dataframe(raw_deals, "deals")
        wo_df, wo_quality = clean_dataframe(raw_wo, "work_orders")

        summary = leadership_summary(deals_df, wo_df)

        return jsonify({
            "summary": summary,
            "data_quality": {
                "deals": deals_quality,
                "work_orders": wo_quality,
            },
        })

    except Exception as e:
        logger.exception(f"Error generating summary: {e}")
        return jsonify({"error": str(e)}), 500
