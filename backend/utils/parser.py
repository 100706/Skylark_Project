"""
Response Formatting Utilities

Handles formatting of currency, percentages, and metric cards for display.
"""

import math


def format_currency(value: float, use_indian: bool = True) -> str:
    """
    Format a number as Indian Rupee currency.
    
    - Values >= 1 Cr  -> ₹X.XX Cr
    - Values >= 1 Lakh -> ₹X.XX L
    - Values >= 1000   -> ₹X,XXX (with Indian grouping)
    - Otherwise        -> ₹X.XX
    """
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "₹0"
    
    value = float(value)
    
    if abs(value) >= 1_00_00_000:  # 1 Crore
        return f"₹{value / 1_00_00_000:.2f} Cr"
    elif abs(value) >= 1_00_000:  # 1 Lakh
        return f"₹{value / 1_00_000:.2f} L"
    elif abs(value) >= 1000:
        # Indian number grouping
        return f"₹{_indian_format(value)}"
    else:
        return f"₹{value:,.2f}"


def _indian_format(number: float) -> str:
    """Format a number using Indian grouping (e.g., 12,50,000)."""
    is_negative = number < 0
    number = abs(number)
    
    integer_part = int(number)
    decimal_part = number - integer_part
    
    s = str(integer_part)
    if len(s) > 3:
        last_three = s[-3:]
        remaining = s[:-3]
        # Group remaining digits in pairs from right
        groups = []
        while remaining:
            groups.append(remaining[-2:])
            remaining = remaining[:-2]
        groups.reverse()
        result = ",".join(groups) + "," + last_three
    else:
        result = s
    
    if decimal_part > 0:
        result += f".{int(decimal_part * 100):02d}"
    
    return f"-{result}" if is_negative else result


def format_percentage(value: float, decimals: int = 1) -> str:
    """Format a number as a percentage string."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "0%"
    return f"{value:.{decimals}f}%"


def format_count(value: int) -> str:
    """Format a count with commas."""
    if value is None:
        return "0"
    return f"{int(value):,}"


def format_metric_card(title: str, value: str, trend: str = None, trend_direction: str = None) -> dict:
    """
    Create a structured metric card for the frontend.
    
    Args:
        title: Metric name (e.g., "Total Revenue")
        value: Formatted value string (e.g., "₹12.5 Cr")
        trend: Trend description (e.g., "+18% QoQ")
        trend_direction: "up", "down", or "neutral"
    
    Returns:
        Dict ready for JSON serialization to frontend.
    """
    card = {
        "title": title,
        "value": value,
    }
    if trend:
        card["trend"] = trend
        card["trend_direction"] = trend_direction or "neutral"
    return card
