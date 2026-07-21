"""
Business Calculation Engine

ALL business metrics are computed here using Pandas.
The LLM NEVER computes these — it only explains/narrates results from this module.

Functions are organized by domain:
- Revenue metrics (from Deals)
- Pipeline metrics (from Deals)
- Work Order metrics (from Work Orders)
- Cross-board analysis (joining both)
- Leadership summary (aggregated KPIs)
"""

import logging
from typing import Optional

import pandas as pd
import numpy as np

from utils.parser import format_currency, format_percentage, format_count, format_metric_card

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Revenue Metrics (Deals Board)
# ---------------------------------------------------------------------------

def total_revenue(deals_df: pd.DataFrame) -> dict:
    """
    Total revenue from Won deals.
    Uses 'Masked Deal value' column, filtered to Deal Status = 'Won'.
    """
    won = deals_df[deals_df["Deal Status"].str.lower() == "won"]
    total = won["Masked Deal value"].sum()
    count = len(won)

    return {
        "total_revenue": float(total),
        "total_revenue_formatted": format_currency(total),
        "won_deal_count": count,
        "average_deal_size": float(total / count) if count > 0 else 0,
        "average_deal_size_formatted": format_currency(total / count) if count > 0 else "₹0",
    }


def revenue_by_sector(deals_df: pd.DataFrame) -> dict:
    """Revenue breakdown by sector from Won deals."""
    sector_col = "Sector/service" if "Sector/service" in deals_df.columns else "Sector"
    won = deals_df[deals_df["Deal Status"].str.lower() == "won"]

    if won.empty:
        return {"sectors": [], "total_revenue": 0}

    breakdown = (
        won.groupby(sector_col)["Masked Deal value"]
        .agg(["sum", "count"])
        .reset_index()
        .rename(columns={"sum": "revenue", "count": "deal_count", sector_col: "sector"})
        .sort_values("revenue", ascending=False)
    )

    sectors = []
    total = breakdown["revenue"].sum()
    for _, row in breakdown.iterrows():
        share = (row["revenue"] / total * 100) if total > 0 else 0
        sectors.append({
            "sector": row["sector"],
            "revenue": float(row["revenue"]),
            "revenue_formatted": format_currency(row["revenue"]),
            "deal_count": int(row["deal_count"]),
            "share_percentage": round(share, 1),
        })

    return {
        "sectors": sectors,
        "total_revenue": float(total),
        "top_sector": sectors[0]["sector"] if sectors else "N/A",
    }


# ---------------------------------------------------------------------------
# Pipeline Metrics (Deals Board)
# ---------------------------------------------------------------------------

def pipeline_value(deals_df: pd.DataFrame) -> dict:
    """
    Total pipeline value from Open deals (not Won, not Dead).
    """
    open_deals = deals_df[deals_df["Deal Status"].str.lower().isin(["open", "on hold"])]
    total = open_deals["Masked Deal value"].sum()
    count = len(open_deals)

    # Breakdown by stage
    stage_breakdown = (
        open_deals.groupby("Deal Stage")["Masked Deal value"]
        .agg(["sum", "count"])
        .reset_index()
        .rename(columns={"sum": "value", "count": "deal_count"})
        .sort_values("value", ascending=False)
    )

    stages = []
    for _, row in stage_breakdown.iterrows():
        stages.append({
            "stage": row["Deal Stage"],
            "value": float(row["value"]),
            "value_formatted": format_currency(row["value"]),
            "deal_count": int(row["deal_count"]),
        })

    # Weighted pipeline (by closure probability)
    weighted = _weighted_pipeline(open_deals)

    return {
        "total_pipeline_value": float(total),
        "total_pipeline_formatted": format_currency(total),
        "open_deal_count": count,
        "stages": stages,
        "weighted_pipeline_value": weighted["value"],
        "weighted_pipeline_formatted": format_currency(weighted["value"]),
    }


def _weighted_pipeline(deals_df: pd.DataFrame) -> dict:
    """Calculate probability-weighted pipeline value."""
    weight_map = {"high": 0.75, "medium": 0.50, "low": 0.25}

    if "Closure Probability" not in deals_df.columns:
        return {"value": 0}

    total_weighted = 0
    for _, row in deals_df.iterrows():
        prob = str(row.get("Closure Probability", "")).lower().strip()
        weight = weight_map.get(prob, 0.5)  # Default 50% for unknown
        val = float(row.get("Masked Deal value", 0) or 0)
        total_weighted += val * weight

    return {"value": float(total_weighted)}


def conversion_rate(deals_df: pd.DataFrame) -> dict:
    """Deal conversion rate: Won / (Won + Dead)."""
    status = deals_df["Deal Status"].str.lower()
    won = (status == "won").sum()
    dead = (status == "dead").sum()
    total_closed = won + dead

    rate = (won / total_closed * 100) if total_closed > 0 else 0

    return {
        "conversion_rate": round(rate, 1),
        "conversion_rate_formatted": format_percentage(rate),
        "won_count": int(won),
        "dead_count": int(dead),
        "total_closed": int(total_closed),
    }


def average_deal_size(deals_df: pd.DataFrame) -> dict:
    """Average deal size across all deals with a value."""
    valid = deals_df[deals_df["Masked Deal value"] > 0]
    avg = valid["Masked Deal value"].mean() if len(valid) > 0 else 0
    median = valid["Masked Deal value"].median() if len(valid) > 0 else 0

    return {
        "average_deal_size": float(avg),
        "average_deal_size_formatted": format_currency(avg),
        "median_deal_size": float(median),
        "median_deal_size_formatted": format_currency(median),
        "deals_with_value": len(valid),
    }


def deals_by_sector(deals_df: pd.DataFrame) -> dict:
    """All deals (not just Won) broken down by sector."""
    sector_col = "Sector/service" if "Sector/service" in deals_df.columns else "Sector"

    breakdown = (
        deals_df.groupby(sector_col)
        .agg(
            deal_count=("Deal Name", "count"),
            total_value=("Masked Deal value", "sum"),
            avg_value=("Masked Deal value", "mean"),
        )
        .reset_index()
        .rename(columns={sector_col: "sector"})
        .sort_values("total_value", ascending=False)
    )

    sectors = []
    for _, row in breakdown.iterrows():
        sectors.append({
            "sector": row["sector"],
            "deal_count": int(row["deal_count"]),
            "total_value": float(row["total_value"]),
            "total_value_formatted": format_currency(row["total_value"]),
            "avg_value": float(row["avg_value"]),
            "avg_value_formatted": format_currency(row["avg_value"]),
        })

    return {"sectors": sectors}


# ---------------------------------------------------------------------------
# Work Order Metrics
# ---------------------------------------------------------------------------

def delayed_work_orders(wo_df: pd.DataFrame) -> dict:
    """
    Identify delayed/stuck work orders.
    Looks at Execution Status for "Pause / struck", "Not Started" with past probable dates,
    and Billing Status "Stuck".
    """
    delayed = []

    # Paused/Struck execution
    if "Execution Status" in wo_df.columns:
        stuck_mask = wo_df["Execution Status"].str.lower().str.contains(
            "pause|struck|stuck", na=False
        )
        stuck = wo_df[stuck_mask]
        for _, row in stuck.iterrows():
            delayed.append({
                "name": row.get("Deal name masked", row.get("name", "Unknown")),
                "company": row.get("Customer Name Code", "Unknown"),
                "sector": row.get("Sector", "Unknown"),
                "status": row.get("Execution Status", "Unknown"),
                "reason": "Execution paused/struck",
                "value": float(row.get("Amount in Rupees (Excl of GST) (Masked)", 0) or 0),
            })

    # Not started but past probable start date
    if "Execution Status" in wo_df.columns and "Probable Start Date" in wo_df.columns:
        not_started = wo_df[
            (wo_df["Execution Status"].str.lower().str.contains("not started", na=False))
            & (wo_df["Probable Start Date"].notna())
            & (wo_df["Probable Start Date"] < pd.Timestamp.now())
        ]
        for _, row in not_started.iterrows():
            delayed.append({
                "name": row.get("Deal name masked", row.get("name", "Unknown")),
                "company": row.get("Customer Name Code", "Unknown"),
                "sector": row.get("Sector", "Unknown"),
                "status": "Not Started (Overdue)",
                "reason": f"Should have started by {row['Probable Start Date'].strftime('%d %b %Y')}",
                "value": float(row.get("Amount in Rupees (Excl of GST) (Masked)", 0) or 0),
            })

    total_delayed_value = sum(d["value"] for d in delayed)

    return {
        "delayed_count": len(delayed),
        "delayed_orders": delayed[:20],  # Cap at 20 for response size
        "total_delayed_value": float(total_delayed_value),
        "total_delayed_value_formatted": format_currency(total_delayed_value),
    }


def work_orders_by_status(wo_df: pd.DataFrame) -> dict:
    """Breakdown of work orders by execution status."""
    if "Execution Status" not in wo_df.columns:
        return {"statuses": []}

    breakdown = (
        wo_df.groupby("Execution Status")
        .agg(
            count=("Execution Status", "count"),
            total_value=("Amount in Rupees (Excl of GST) (Masked)", "sum"),
        )
        .reset_index()
        .sort_values("count", ascending=False)
    )

    statuses = []
    for _, row in breakdown.iterrows():
        statuses.append({
            "status": row["Execution Status"],
            "count": int(row["count"]),
            "total_value": float(row["total_value"]),
            "total_value_formatted": format_currency(row["total_value"]),
        })

    return {"statuses": statuses, "total_work_orders": len(wo_df)}


def work_orders_by_sector(wo_df: pd.DataFrame) -> dict:
    """Breakdown of work orders by sector."""
    if "Sector" not in wo_df.columns:
        return {"sectors": []}

    breakdown = (
        wo_df.groupby("Sector")
        .agg(
            count=("Sector", "count"),
            total_value=("Amount in Rupees (Excl of GST) (Masked)", "sum"),
        )
        .reset_index()
        .sort_values("total_value", ascending=False)
    )

    sectors = []
    for _, row in breakdown.iterrows():
        sectors.append({
            "sector": row["Sector"],
            "count": int(row["count"]),
            "total_value": float(row["total_value"]),
            "total_value_formatted": format_currency(row["total_value"]),
        })

    return {"sectors": sectors}


def billing_summary(wo_df: pd.DataFrame) -> dict:
    """Billing and collection summary from work orders."""
    total_order_value = wo_df["Amount in Rupees (Excl of GST) (Masked)"].sum()
    total_billed = wo_df["Billed Value in Rupees (Excl of GST.) (Masked)"].sum() if "Billed Value in Rupees (Excl of GST.) (Masked)" in wo_df.columns else 0
    total_collected = wo_df["Collected Amount in Rupees (Incl of GST.) (Masked)"].sum() if "Collected Amount in Rupees (Incl of GST.) (Masked)" in wo_df.columns else 0
    total_receivable = wo_df["Amount Receivable (Masked)"].sum() if "Amount Receivable (Masked)" in wo_df.columns else 0
    total_to_bill = wo_df["Amount to be billed in Rs. (Exl. of GST) (Masked)"].sum() if "Amount to be billed in Rs. (Exl. of GST) (Masked)" in wo_df.columns else 0

    billing_rate = (total_billed / total_order_value * 100) if total_order_value > 0 else 0
    collection_rate = (total_collected / total_billed * 100) if total_billed > 0 else 0

    return {
        "total_order_value": float(total_order_value),
        "total_order_value_formatted": format_currency(total_order_value),
        "total_billed": float(total_billed),
        "total_billed_formatted": format_currency(total_billed),
        "total_collected": float(total_collected),
        "total_collected_formatted": format_currency(total_collected),
        "total_receivable": float(total_receivable),
        "total_receivable_formatted": format_currency(total_receivable),
        "total_to_bill": float(total_to_bill),
        "total_to_bill_formatted": format_currency(total_to_bill),
        "billing_rate": round(billing_rate, 1),
        "billing_rate_formatted": format_percentage(billing_rate),
        "collection_rate": round(collection_rate, 1),
        "collection_rate_formatted": format_percentage(collection_rate),
    }


# ---------------------------------------------------------------------------
# Cross-Board Analysis
# ---------------------------------------------------------------------------

def top_clients(deals_df: pd.DataFrame, wo_df: pd.DataFrame) -> dict:
    """
    Top clients by combined deal value and work order value.
    Joins on normalized company name.
    """
    # Aggregate deals by client
    deal_agg = (
        deals_df.groupby("_normalized_company")
        .agg(
            deal_value=("Masked Deal value", "sum"),
            deal_count=("Deal Name", "count"),
            client_code=("Client Code", "first"),
        )
        .reset_index()
    )

    # Aggregate work orders by client
    wo_agg = (
        wo_df.groupby("_normalized_company")
        .agg(
            wo_value=("Amount in Rupees (Excl of GST) (Masked)", "sum"),
            wo_count=("_normalized_company", "count"),
            customer_code=("Customer Name Code", "first"),
        )
        .reset_index()
    )

    # Merge on normalized company name
    merged = pd.merge(deal_agg, wo_agg, on="_normalized_company", how="outer").fillna(0)
    merged["total_value"] = merged["deal_value"] + merged["wo_value"]
    merged = merged.sort_values("total_value", ascending=False)

    clients = []
    for _, row in merged.head(10).iterrows():
        name = row.get("client_code") or row.get("customer_code") or row["_normalized_company"]
        clients.append({
            "client": str(name),
            "deal_value": float(row["deal_value"]),
            "deal_value_formatted": format_currency(row["deal_value"]),
            "deal_count": int(row["deal_count"]),
            "wo_value": float(row["wo_value"]),
            "wo_value_formatted": format_currency(row["wo_value"]),
            "wo_count": int(row["wo_count"]),
            "total_value": float(row["total_value"]),
            "total_value_formatted": format_currency(row["total_value"]),
        })

    return {"top_clients": clients}


def cross_board_analysis(deals_df: pd.DataFrame, wo_df: pd.DataFrame) -> dict:
    """
    Cross-board insights:
    - Clients with deals but no work orders (potential conversion gap)
    - Clients with work orders but no deals (retention risk)
    - Clients with both (active relationships)
    """
    deal_clients = set(deals_df["_normalized_company"].dropna().unique())
    wo_clients = set(wo_df["_normalized_company"].dropna().unique())

    deals_only = deal_clients - wo_clients
    wo_only = wo_clients - deal_clients
    both = deal_clients & wo_clients

    return {
        "clients_with_both": len(both),
        "clients_deals_only": len(deals_only),
        "clients_wo_only": len(wo_only),
        "deals_only_list": sorted(list(deals_only))[:10],
        "wo_only_list": sorted(list(wo_only))[:10],
        "insight": _cross_board_insight(deals_only, wo_only, both),
    }


def _cross_board_insight(deals_only, wo_only, both) -> str:
    """Generate a brief cross-board insight string."""
    parts = []
    if deals_only:
        parts.append(f"{len(deals_only)} clients have deals but no work orders yet (conversion opportunity)")
    if wo_only:
        parts.append(f"{len(wo_only)} clients have work orders but no active deals (upsell opportunity)")
    if both:
        parts.append(f"{len(both)} clients have active relationships across both")
    return "; ".join(parts) if parts else "No cross-board patterns detected"


# ---------------------------------------------------------------------------
# Leadership Summary
# ---------------------------------------------------------------------------

def leadership_summary(deals_df: pd.DataFrame, wo_df: pd.DataFrame) -> dict:
    """
    Aggregated KPIs for a leadership/executive summary.
    Combines the most important metrics from both boards.
    """
    rev = total_revenue(deals_df)
    pipe = pipeline_value(deals_df)
    conv = conversion_rate(deals_df)
    delayed = delayed_work_orders(wo_df)
    billing = billing_summary(wo_df)
    rev_sector = revenue_by_sector(deals_df)
    wo_status = work_orders_by_status(wo_df)
    cross = cross_board_analysis(deals_df, wo_df)

    return {
        "headline_metrics": {
            "total_revenue": rev,
            "pipeline": pipe,
            "conversion_rate": conv,
            "delayed_projects": {
                "count": delayed["delayed_count"],
                "value": delayed["total_delayed_value"],
                "value_formatted": delayed["total_delayed_value_formatted"],
            },
            "top_sector": rev_sector.get("top_sector", "N/A"),
            "total_work_orders": wo_status.get("total_work_orders", 0),
        },
        "billing": billing,
        "sector_breakdown": rev_sector,
        "work_order_status": wo_status,
        "cross_board": cross,
        "metric_cards": [
            format_metric_card("Total Revenue", rev["total_revenue_formatted"]),
            format_metric_card("Pipeline Value", pipe["total_pipeline_formatted"]),
            format_metric_card("Weighted Pipeline", pipe["weighted_pipeline_formatted"]),
            format_metric_card("Conversion Rate", conv["conversion_rate_formatted"]),
            format_metric_card("Delayed Projects", str(delayed["delayed_count"])),
            format_metric_card("Open Deals", str(pipe["open_deal_count"])),
            format_metric_card("Total Receivable", billing["total_receivable_formatted"]),
            format_metric_card("Top Sector", rev_sector.get("top_sector", "N/A")),
        ],
    }


# ---------------------------------------------------------------------------
# Intent-to-Function Router
# ---------------------------------------------------------------------------

# Maps intent types to computation functions
INTENT_FUNCTION_MAP = {
    "revenue": lambda d, w: total_revenue(d),
    "revenue_by_sector": lambda d, w: revenue_by_sector(d),
    "pipeline": lambda d, w: pipeline_value(d),
    "conversion": lambda d, w: conversion_rate(d),
    "deal_size": lambda d, w: average_deal_size(d),
    "deals_by_sector": lambda d, w: deals_by_sector(d),
    "delayed": lambda d, w: delayed_work_orders(w),
    "wo_status": lambda d, w: work_orders_by_status(w),
    "wo_by_sector": lambda d, w: work_orders_by_sector(w),
    "billing": lambda d, w: billing_summary(w),
    "top_clients": lambda d, w: top_clients(d, w),
    "cross_board": lambda d, w: cross_board_analysis(d, w),
    "summary": lambda d, w: leadership_summary(d, w),
}


def compute_for_intent(intent_type: str, deals_df: pd.DataFrame, wo_df: pd.DataFrame) -> dict:
    """
    Route an intent type to the appropriate computation function.
    Returns computed metrics dict.
    """
    func = INTENT_FUNCTION_MAP.get(intent_type)
    if not func:
        # Default to leadership summary for unrecognized intents
        logger.warning(f"Unknown intent type '{intent_type}', falling back to summary")
        return leadership_summary(deals_df, wo_df)

    try:
        return func(deals_df, wo_df)
    except Exception as e:
        logger.error(f"Error computing metrics for intent '{intent_type}': {e}")
        return {"error": str(e)}
