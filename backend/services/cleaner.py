"""
Data Cleaning Pipeline

Handles messy real-world data from Monday.com boards:
- Header-row pollution (column names appearing as data values)
- Missing values with per-column-type strategies
- Date normalization across multiple formats
- Sector name inconsistencies
- Currency string parsing
- Duplicate company detection via fuzzy matching

Every cleaning action is tracked in a quality report.
"""

import re
import logging
from datetime import datetime

import pandas as pd
import numpy as np
from rapidfuzz import fuzz

from utils.normalizer import normalize_company_name, normalize_sector

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Main Entry Point
# ---------------------------------------------------------------------------

def clean_dataframe(df: pd.DataFrame, board_type: str) -> tuple[pd.DataFrame, dict]:
    """
    Clean a raw DataFrame from Monday.com.
    
    Args:
        df: Raw DataFrame from items_to_dataframe()
        board_type: "work_orders" or "deals"
    
    Returns:
        (cleaned_df, quality_report)
    """
    if df.empty:
        return df, _empty_report()

    report = {
        "original_rows": len(df),
        "original_columns": len(df.columns),
        "issues_found": [],
        "fixes_applied": [],
    }

    # Step 1: Remove header-row pollution
    df = _remove_header_rows(df, board_type, report)

    # Step 2: Board-specific cleaning
    if board_type == "work_orders":
        df = _clean_work_orders(df, report)
    elif board_type == "deals":
        df = _clean_deals(df, report)

    # Step 3: Universal cleaning
    df = _handle_missing_values(df, report)
    df = _remove_duplicates(df, board_type, report)

    report["final_rows"] = len(df)
    report["final_columns"] = len(df.columns)
    report["data_quality_score"] = _compute_quality_score(df, report)

    logger.info(
        f"Cleaned {board_type}: {report['original_rows']} -> {report['final_rows']} rows, "
        f"quality score: {report['data_quality_score']:.1f}%"
    )
    return df, report


# ---------------------------------------------------------------------------
# Header-Row Pollution Removal
# ---------------------------------------------------------------------------

# These are actual column name strings that appear as data values in both boards
_HEADER_MARKERS = {
    "deals": ["Deal Status", "Deal Stage", "Sector/service", "Closure Probability", "Product deal"],
    "work_orders": ["Execution Status", "Nature of Work", "Sector", "Billing Status"],
}


def _remove_header_rows(df: pd.DataFrame, board_type: str, report: dict) -> pd.DataFrame:
    """Remove rows where column names appear as data values (header pollution)."""
    markers = _HEADER_MARKERS.get(board_type, [])
    if not markers:
        return df

    mask = pd.Series(False, index=df.index)
    for col_name in markers:
        if col_name in df.columns:
            mask = mask | (df[col_name].astype(str).str.strip() == col_name)

    polluted_count = mask.sum()
    if polluted_count > 0:
        report["issues_found"].append(f"Found {polluted_count} header-pollution rows")
        report["fixes_applied"].append(f"Removed {polluted_count} header-pollution rows")
        df = df[~mask].reset_index(drop=True)

    return df


# ---------------------------------------------------------------------------
# Work Orders Specific Cleaning
# ---------------------------------------------------------------------------

_WO_DATE_COLUMNS = [
    "Data Delivery Date",
    "Date of PO/LOI",
    "Probable Start Date",
    "Probable End Date",
    "Last invoice date",
]

_WO_CURRENCY_COLUMNS = [
    "Amount in Rupees (Excl of GST) (Masked)",
    "Amount in Rupees (Incl of GST) (Masked)",
    "Billed Value in Rupees (Excl of GST.) (Masked)",
    "Billed Value in Rupees (Incl of GST.) (Masked)",
    "Collected Amount in Rupees (Incl of GST.) (Masked)",
    "Amount to be billed in Rs. (Exl. of GST) (Masked)",
    "Amount to be billed in Rs. (Incl. of GST) (Masked)",
    "Amount Receivable (Masked)",
]


def _clean_work_orders(df: pd.DataFrame, report: dict) -> pd.DataFrame:
    """Apply Work Orders-specific cleaning."""
    # Normalize dates
    for col in _WO_DATE_COLUMNS:
        if col in df.columns:
            df[col] = normalize_dates(df[col])
            null_count = df[col].isna().sum()
            if null_count > 0:
                report["issues_found"].append(f"{col}: {null_count} unparseable/missing dates")

    # Normalize currency columns
    for col in _WO_CURRENCY_COLUMNS:
        if col in df.columns:
            df[col] = normalize_currency(df[col])

    # Normalize sectors
    if "Sector" in df.columns:
        original_unique = df["Sector"].nunique()
        df["Sector"] = df["Sector"].apply(normalize_sector)
        new_unique = df["Sector"].nunique()
        if new_unique < original_unique:
            report["fixes_applied"].append(
                f"Normalized sectors: {original_unique} -> {new_unique} unique values"
            )

    # Normalize execution status (fix casing inconsistencies)
    if "Execution Status" in df.columns:
        df["Execution Status"] = df["Execution Status"].str.strip().str.title()

    # Add normalized company name for cross-board joining
    if "Customer Name Code" in df.columns:
        df["_normalized_company"] = df["Customer Name Code"].apply(normalize_company_name)

    return df


# ---------------------------------------------------------------------------
# Deals Specific Cleaning
# ---------------------------------------------------------------------------

_DEALS_DATE_COLUMNS = [
    "Close Date (A)",
    "Tentative Close Date",
    "Created Date",
]


def _clean_deals(df: pd.DataFrame, report: dict) -> pd.DataFrame:
    """Apply Deals-specific cleaning."""
    # Normalize dates
    for col in _DEALS_DATE_COLUMNS:
        if col in df.columns:
            df[col] = normalize_dates(df[col])
            null_count = df[col].isna().sum()
            if null_count > 0:
                report["issues_found"].append(f"{col}: {null_count} unparseable/missing dates")

    # Normalize deal value
    if "Masked Deal value" in df.columns:
        df["Masked Deal value"] = normalize_currency(df["Masked Deal value"])

    # Normalize sector
    if "Sector/service" in df.columns:
        original_unique = df["Sector/service"].nunique()
        df["Sector/service"] = df["Sector/service"].apply(normalize_sector)
        new_unique = df["Sector/service"].nunique()
        if new_unique < original_unique:
            report["fixes_applied"].append(
                f"Normalized deal sectors: {original_unique} -> {new_unique} unique values"
            )

    # Normalize deal status
    if "Deal Status" in df.columns:
        df["Deal Status"] = df["Deal Status"].str.strip().str.title()

    # Add normalized company name for cross-board joining
    if "Client Code" in df.columns:
        df["_normalized_company"] = df["Client Code"].apply(normalize_company_name)

    return df


# ---------------------------------------------------------------------------
# Date Normalization
# ---------------------------------------------------------------------------

# Common date formats to try in order
_DATE_FORMATS = [
    "%Y-%m-%d",
    "%d-%m-%Y",
    "%d/%m/%Y",
    "%m/%d/%Y",
    "%Y-%m-%d %H:%M:%S",
    "%d-%m-%Y %H:%M:%S",
    "%d %b %Y",
    "%d %B %Y",
    "%b %d, %Y",
    "%B %d, %Y",
]


def normalize_dates(series: pd.Series) -> pd.Series:
    """
    Normalize a series of dates in various formats to datetime.
    Handles: datetime objects, strings in multiple formats, NaN/None.
    """
    def _parse_single(val):
        if pd.isna(val) or val is None:
            return pd.NaT
        
        # Already a datetime
        if isinstance(val, (datetime, pd.Timestamp)):
            return pd.Timestamp(val)
        
        val_str = str(val).strip()
        if not val_str or val_str.lower() in ("nan", "none", "nat", ""):
            return pd.NaT

        # Try pandas built-in parser first (handles most ISO formats)
        try:
            return pd.to_datetime(val_str, dayfirst=True)
        except (ValueError, TypeError):
            pass

        # Try explicit formats
        for fmt in _DATE_FORMATS:
            try:
                return pd.Timestamp(datetime.strptime(val_str, fmt))
            except ValueError:
                continue

        return pd.NaT

    return series.apply(_parse_single)


# ---------------------------------------------------------------------------
# Currency Normalization
# ---------------------------------------------------------------------------

_CURRENCY_PATTERN = re.compile(r"[₹$,\s]")


def normalize_currency(series: pd.Series) -> pd.Series:
    """
    Normalize currency values:
    - Strip ₹, $, commas
    - Convert 'Cr'/'L'/'Lakh'/'Crore' suffixes
    - Convert to float
    """
    def _parse_single(val):
        if pd.isna(val) or val is None:
            return 0.0

        # Already numeric
        if isinstance(val, (int, float)):
            return float(val) if not np.isnan(val) else 0.0

        val_str = str(val).strip()
        if not val_str or val_str.lower() in ("nan", "none", ""):
            return 0.0

        # Remove currency symbols and commas
        val_str = _CURRENCY_PATTERN.sub("", val_str)

        # Handle Cr/Lakh suffixes
        multiplier = 1.0
        val_lower = val_str.lower()
        if "cr" in val_lower:
            multiplier = 1_00_00_000
            val_str = re.sub(r"(?i)\s*cr(ore)?s?\s*", "", val_str)
        elif "l" in val_lower and "lakh" in val_lower:
            multiplier = 1_00_000
            val_str = re.sub(r"(?i)\s*lakhs?\s*", "", val_str)

        try:
            return float(val_str) * multiplier
        except ValueError:
            return 0.0

    return series.apply(_parse_single)


# ---------------------------------------------------------------------------
# Missing Value Handling
# ---------------------------------------------------------------------------

def _handle_missing_values(df: pd.DataFrame, report: dict) -> pd.DataFrame:
    """
    Handle missing values with per-column-type strategy.
    - Numeric columns: fill with 0
    - Text columns: fill with "Unknown"
    - Date columns: leave as NaT
    Never silently drop rows.
    """
    total_missing = df.isna().sum().sum()
    if total_missing > 0:
        report["issues_found"].append(f"Total missing values: {total_missing}")

    for col in df.columns:
        if col.startswith("_"):  # Skip internal columns
            continue
        
        null_count = df[col].isna().sum()
        if null_count == 0:
            continue

        dtype = df[col].dtype
        if pd.api.types.is_numeric_dtype(dtype):
            df[col] = df[col].fillna(0)
            report["fixes_applied"].append(f"{col}: filled {null_count} nulls with 0")
        elif pd.api.types.is_datetime64_any_dtype(dtype):
            pass  # Leave dates as NaT — they indicate genuinely missing data
        else:
            df[col] = df[col].fillna("Unknown")
            report["fixes_applied"].append(f"{col}: filled {null_count} nulls with 'Unknown'")

    return df


# ---------------------------------------------------------------------------
# Duplicate Removal
# ---------------------------------------------------------------------------

def _remove_duplicates(df: pd.DataFrame, board_type: str, report: dict) -> pd.DataFrame:
    """
    Remove exact duplicates. 
    Fuzzy dedup on company name is intentionally NOT done here — 
    we keep distinct rows but use _normalized_company for aggregation joins.
    """
    original_len = len(df)
    
    # Determine key columns for dedup
    if board_type == "work_orders":
        subset = ["Serial #"] if "Serial #" in df.columns else None
    elif board_type == "deals":
        # Deal Name + Client Code + Deal Stage should be unique
        subset_candidates = ["Deal Name", "Client Code", "Deal Stage"]
        subset = [c for c in subset_candidates if c in df.columns] or None
    else:
        subset = None
    
    df = df.drop_duplicates(subset=subset, keep="first").reset_index(drop=True)
    
    removed = original_len - len(df)
    if removed > 0:
        report["fixes_applied"].append(f"Removed {removed} duplicate rows")
    
    return df


# ---------------------------------------------------------------------------
# Quality Score
# ---------------------------------------------------------------------------

def _compute_quality_score(df: pd.DataFrame, report: dict) -> float:
    """
    Compute a 0-100 data quality score.
    Based on: completeness, consistency, and fixes applied.
    """
    if df.empty:
        return 0.0

    # Completeness: % of non-null cells (excluding internal cols)
    data_cols = [c for c in df.columns if not c.startswith("_")]
    if data_cols:
        total_cells = len(df) * len(data_cols)
        non_null_cells = df[data_cols].notna().sum().sum()
        completeness = (non_null_cells / total_cells) * 100
    else:
        completeness = 100.0

    # Penalty for issues found (each issue deducts up to 5 points)
    issue_penalty = min(len(report.get("issues_found", [])) * 3, 25)

    score = max(0, min(100, completeness - issue_penalty))
    return round(score, 1)


def _empty_report() -> dict:
    """Return a quality report for an empty DataFrame."""
    return {
        "original_rows": 0,
        "original_columns": 0,
        "final_rows": 0,
        "final_columns": 0,
        "issues_found": ["No data available"],
        "fixes_applied": [],
        "data_quality_score": 0.0,
    }
