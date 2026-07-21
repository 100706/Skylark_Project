"""
Monday.com API Client

Handles all communication with the Monday.com GraphQL API.
Dynamic board discovery, paginated item fetching, and DataFrame conversion.
"""

import os
import logging
import requests
import pandas as pd
from rapidfuzz import fuzz

logger = logging.getLogger(__name__)

MONDAY_API_URL = "https://api.monday.com/v2"


def _get_headers():
    """Build auth headers from environment."""
    token = os.getenv("MONDAY_API_TOKEN")
    if not token:
        raise ValueError("MONDAY_API_TOKEN environment variable is not set")
    return {
        "Authorization": token,
        "Content-Type": "application/json",
    }


def _execute_query(query: str, variables: dict = None) -> dict:
    """
    Execute a GraphQL query against the Monday.com API.
    Raises on HTTP errors or GraphQL-level errors.
    """
    payload = {"query": query}
    if variables:
        payload["variables"] = variables

    response = requests.post(
        MONDAY_API_URL,
        json=payload,
        headers=_get_headers(),
        timeout=30,
    )
    response.raise_for_status()

    data = response.json()
    if "errors" in data:
        error_msgs = [e.get("message", str(e)) for e in data["errors"]]
        raise RuntimeError(f"Monday.com API errors: {'; '.join(error_msgs)}")

    return data.get("data", {})


# ---------------------------------------------------------------------------
# Board Discovery
# ---------------------------------------------------------------------------

def list_boards(limit: int = 50) -> list[dict]:
    """
    List all accessible boards. Returns list of {id, name, state}.
    """
    query = """
    query ($limit: Int!) {
        boards(limit: $limit, state: active) {
            id
            name
            state
        }
    }
    """
    data = _execute_query(query, {"limit": limit})
    boards = data.get("boards", [])
    logger.info(f"Discovered {len(boards)} active boards")
    return boards


def find_board_by_name(target_name: str, env_override_key: str = None) -> dict:
    """
    Find a board by fuzzy name matching.
    
    If env_override_key is set (e.g. 'WORK_ORDERS_BOARD_ID'), check env first
    as a demo-day safety net. Otherwise, fuzzy-match against all boards.
    
    Returns {id, name} or None.
    """
    # Demo-day safety net: check for hardcoded board ID in env
    if env_override_key:
        override_id = os.getenv(env_override_key)
        if override_id:
            logger.info(f"Using env override {env_override_key}={override_id}")
            return {"id": override_id, "name": target_name}

    # Dynamic discovery via fuzzy matching
    boards = list_boards()
    best_match = None
    best_score = 0

    for board in boards:
        score = fuzz.ratio(target_name.lower(), board["name"].lower())
        if score > best_score:
            best_score = score
            best_match = board

    if best_match and best_score >= 60:
        logger.info(
            f"Matched '{target_name}' -> '{best_match['name']}' "
            f"(id={best_match['id']}, score={best_score})"
        )
        return {"id": best_match["id"], "name": best_match["name"]}

    logger.warning(f"No board found matching '{target_name}' (best score: {best_score})")
    return None


# ---------------------------------------------------------------------------
# Schema Inspection
# ---------------------------------------------------------------------------

def fetch_board_schema(board_id: str) -> list[dict]:
    """
    Fetch column definitions for a board. 
    Returns list of {id, title, type}.
    """
    query = """
    query ($boardId: [ID!]!) {
        boards(ids: $boardId) {
            columns {
                id
                title
                type
            }
        }
    }
    """
    data = _execute_query(query, {"boardId": [board_id]})
    boards = data.get("boards", [])
    if not boards:
        return []
    return boards[0].get("columns", [])


# ---------------------------------------------------------------------------
# Item Fetching (Paginated)
# ---------------------------------------------------------------------------

def fetch_board_items(board_id: str, limit: int = 500) -> tuple[list[dict], list[dict]]:
    """
    Fetch ALL items from a board using cursor-based pagination.
    
    Returns (items, columns) where:
    - items: list of flattened dicts (item name + all column values as text)
    - columns: list of {id, title, type} for schema reference
    """
    # First page
    first_query = """
    query ($boardId: [ID!]!, $limit: Int!) {
        boards(ids: $boardId) {
            columns {
                id
                title
                type
            }
            items_page(limit: $limit) {
                cursor
                items {
                    id
                    name
                    column_values {
                        id
                        title
                        text
                        type
                    }
                }
            }
        }
    }
    """
    data = _execute_query(first_query, {"boardId": [board_id], "limit": limit})
    boards = data.get("boards", [])
    if not boards:
        return [], []

    board = boards[0]
    columns = board.get("columns", [])
    items_page = board.get("items_page", {})
    raw_items = items_page.get("items", [])
    cursor = items_page.get("cursor")

    # Paginate through remaining items
    while cursor:
        next_query = """
        query ($limit: Int!, $cursor: String!) {
            next_items_page(limit: $limit, cursor: $cursor) {
                cursor
                items {
                    id
                    name
                    column_values {
                        id
                        title
                        text
                        type
                    }
                }
            }
        }
        """
        page_data = _execute_query(next_query, {"limit": limit, "cursor": cursor})
        next_page = page_data.get("next_items_page", {})
        raw_items.extend(next_page.get("items", []))
        cursor = next_page.get("cursor")
        logger.info(f"Fetched page, total items so far: {len(raw_items)}")

    # Flatten column_values into dicts
    items = _flatten_items(raw_items)
    logger.info(f"Fetched {len(items)} items from board {board_id}")
    return items, columns


def _flatten_items(raw_items: list[dict]) -> list[dict]:
    """
    Convert Monday.com's nested column_values structure into flat dicts.
    Each item becomes: {name: ..., col_title_1: text_1, col_title_2: text_2, ...}
    """
    flattened = []
    for item in raw_items:
        row = {
            "_item_id": item["id"],
            "name": item["name"],
        }
        for cv in item.get("column_values", []):
            # Use column title as key, text as value
            title = cv.get("title", cv.get("id", "unknown"))
            row[title] = cv.get("text", "")
        flattened.append(row)
    return flattened


# ---------------------------------------------------------------------------
# DataFrame Conversion
# ---------------------------------------------------------------------------

def items_to_dataframe(items: list[dict]) -> pd.DataFrame:
    """Convert flattened Monday items to a Pandas DataFrame."""
    if not items:
        return pd.DataFrame()
    df = pd.DataFrame(items)
    logger.info(f"Created DataFrame: {df.shape[0]} rows x {df.shape[1]} columns")
    return df


# ---------------------------------------------------------------------------
# High-Level Fetchers
# ---------------------------------------------------------------------------

def fetch_work_orders() -> pd.DataFrame:
    """Fetch and return Work Orders board as a DataFrame."""
    board_name = os.getenv("WORK_ORDERS_BOARD_NAME", "Work Orders")
    board = find_board_by_name(board_name, env_override_key="WORK_ORDERS_BOARD_ID")
    if not board:
        logger.warning(f"Could not find board '{board_name}', falling back to local Excel file")
        import pathlib
        file_path = pathlib.Path(__file__).parent.parent.parent / "Work_Order_Tracker Data.xlsx"
        if file_path.exists():
            return pd.read_excel(file_path, header=1)
        raise ValueError(f"Could not find board matching '{board_name}' and no local fallback found")
    
    items, _ = fetch_board_items(board["id"])
    return items_to_dataframe(items)


def fetch_deals() -> pd.DataFrame:
    """Fetch and return Deals board as a DataFrame."""
    board_name = os.getenv("DEALS_BOARD_NAME", "Deals")
    board = find_board_by_name(board_name, env_override_key="DEALS_BOARD_ID")
    if not board:
        logger.warning(f"Could not find board '{board_name}', falling back to local Excel file")
        import pathlib
        file_path = pathlib.Path(__file__).parent.parent.parent / "Deal funnel Data.xlsx"
        if file_path.exists():
            return pd.read_excel(file_path)
        raise ValueError(f"Could not find board matching '{board_name}' and no local fallback found")
    
    items, _ = fetch_board_items(board["id"])
    return items_to_dataframe(items)
