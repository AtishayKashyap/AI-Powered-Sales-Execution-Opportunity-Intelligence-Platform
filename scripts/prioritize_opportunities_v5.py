#!/usr/bin/env python3
"""
SalesForge — V5 Opportunity Prioritization

Adds an operational priority layer on top of the frozen V5 detector.
The detector answers: "What opportunity exists?"
This layer answers: "Which opportunities should a sales rep act on first?"

No ground-truth labels are used for prioritization.

Input:
  data/processed_v5/opportunities_v5.csv
  data/processed_v5/outlet_features.csv

Output:
  data/processed_v5/prioritized_opportunities_v5.csv

The priority score is opportunity-type-specific and uses only evidence
already emitted by the frozen detector plus outlet-level value/context.
"""

from pathlib import Path
import json
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OPP = ROOT / "data" / "processed_v5" / "opportunities_v5.csv"
FEATURES = ROOT / "data" / "processed_v5" / "outlet_features.csv"
OUT = ROOT / "data" / "processed_v5" / "prioritized_opportunities_v5.csv"


def clamp01(x):
    return np.clip(x, 0.0, 1.0)


def safe_series(df, col, default=0.0):
    if col in df.columns:
        return pd.to_numeric(df[col], errors="coerce").fillna(default)
    return pd.Series(default, index=df.index, dtype=float)


def parse_evidence(x):
    try:
        return json.loads(x) if isinstance(x, str) else {}
    except Exception:
        return {}


def minmax(s):
    s = pd.to_numeric(s, errors="coerce").fillna(0.0)
    lo, hi = float(s.min()), float(s.max())
    if hi <= lo:
        return pd.Series(0.5, index=s.index)
    return clamp01((s - lo) / (hi - lo))


def percentile_score(s):
    """
    Rank-based normalization is more robust to extreme synthetic values
    than raw min-max scaling.
    """
    s = pd.to_numeric(s, errors="coerce").fillna(0.0)
    if len(s) <= 1:
        return pd.Series(0.5, index=s.index)
    return s.rank(method="average", pct=True).fillna(0.5)


def extract_evidence(opp):
    evidence = opp["evidence"].apply(parse_evidence)
    ev = pd.json_normalize(evidence)
    ev.index = opp.index
    for col in ev.columns:
        opp[f"ev_{col}"] = ev[col]
    return opp


def revenue_priority(df):
    decline = clamp01(
        -safe_series(df, "ev_revenue_growth_30d") / 1.0
    )
    gap = percentile_score(
        safe_series(df, "ev_revenue_gap_vs_previous_30d")
    )
    peer = clamp01(
        1.0 - safe_series(df, "ev_revenue_index_vs_peer")
    )
    frequency = clamp01(
        (
            safe_series(df, "ev_orders_previous_30d")
            - safe_series(df, "ev_orders_30d")
        )
        / safe_series(df, "ev_orders_previous_30d", 1.0).replace(0, 1)
    )

    # Revenue gap is the main business-value signal; decline severity,
    # peer underperformance and order-frequency deterioration provide context.
    raw = (
        0.40 * gap
        + 0.30 * decline
        + 0.20 * peer
        + 0.10 * frequency
    )
    return 100.0 * clamp01(raw)


def inactive_priority(df):
    historical_value = percentile_score(
        safe_series(df, "ev_revenue_previous_30d")
    )
    days = clamp01(
        (safe_series(df, "ev_days_since_last_order") - 30.0) / 30.0
    )
    days = np.maximum(days, 0.0)
    historical_orders = percentile_score(
        safe_series(df, "ev_orders_previous_30d")
    )

    raw = (
        0.60 * historical_value
        + 0.25 * days
        + 0.15 * historical_orders
    )
    return 100.0 * clamp01(raw)


def stock_priority(df):
    events = percentile_score(
        safe_series(df, "ev_stockout_events_90d")
    )
    rate = percentile_score(
        safe_series(df, "ev_stockout_rate_90d")
    )
    low_stock = clamp01(
        1.0 - safe_series(df, "ev_avg_closing_stock_90d") / 3.0
    )

    raw = (
        0.40 * events
        + 0.35 * rate
        + 0.25 * low_stock
    )
    return 100.0 * clamp01(raw)


def cross_sell_priority(df):
    # Lower rank number means stronger territory demand.
    rank = safe_series(df, "ev_territory_category_rank")
    rank_strength = clamp01((6.0 - rank) / 5.0)

    demand = percentile_score(
        safe_series(df, "ev_territory_category_orders_90d")
    )

    # A smaller current assortment means more room to expand.
    assortment = clamp01(
        1.0 - safe_series(df, "ev_current_category_count_90d") / 4.0
    )

    raw = (
        0.45 * demand
        + 0.35 * rank_strength
        + 0.20 * assortment
    )
    return 100.0 * clamp01(raw)


def priority_band(score):
    if score >= 80:
        return "P1"
    if score >= 65:
        return "P2"
    return "P3"


def action_urgency(score):
    if score >= 80:
        return "Immediate"
    if score >= 65:
        return "Planned"
    return "Monitor"


def main():
    print("SALESFORGE — V5 OPPORTUNITY PRIORITIZATION")
    print("=" * 78)

    if not OPP.exists():
        raise FileNotFoundError(f"Missing opportunities file: {OPP}")
    if not FEATURES.exists():
        raise FileNotFoundError(f"Missing feature store: {FEATURES}")

    opp = pd.read_csv(OPP)
    features = pd.read_csv(FEATURES)

    print(f"Detected opportunities: {len(opp):,}")
    print(f"Feature rows: {len(features):,}")

    # Join outlet context. We deliberately do not use ground truth.
    feature_cols = [
        "outlet_id",
        "revenue_30d",
        "revenue_previous_30d",
        "revenue_per_visit_30d",
        "target_achievement_pct",
        "revenue_index_vs_peer",
        "visits_30d",
        "productive_visits_30d",
    ]
    feature_cols = [c for c in feature_cols if c in features.columns]

    context = features[feature_cols].drop_duplicates("outlet_id")
    df = opp.merge(context, on="outlet_id", how="left", suffixes=("", "_feature"))

    df = extract_evidence(df)

    df["priority_score"] = np.nan

    masks = {
        "Revenue Recovery": df["opportunity_type"].eq("Revenue Recovery"),
        "Inactive Outlet": df["opportunity_type"].eq("Inactive Outlet"),
        "Stock Risk": df["opportunity_type"].eq("Stock Risk"),
        "Cross-Sell": df["opportunity_type"].eq("Cross-Sell"),
    }

    for typ, mask in masks.items():
        sub = df.loc[mask]
        if sub.empty:
            continue

        if typ == "Revenue Recovery":
            scores = revenue_priority(sub)
        elif typ == "Inactive Outlet":
            scores = inactive_priority(sub)
        elif typ == "Stock Risk":
            scores = stock_priority(sub)
        else:
            scores = cross_sell_priority(sub)

        df.loc[mask, "priority_score"] = scores

    # Safety fallback for unexpected types.
    df["priority_score"] = (
        pd.to_numeric(df["priority_score"], errors="coerce")
        .fillna(pd.to_numeric(df["score"], errors="coerce").fillna(0))
        .clip(0, 100)
        .round(2)
    )

    df["priority_band"] = df["priority_score"].apply(priority_band)
    df["action_urgency"] = df["priority_score"].apply(action_urgency)

    # Rank globally and within opportunity type.
    df["global_rank"] = (
        df["priority_score"]
        .rank(method="first", ascending=False)
        .astype(int)
    )
    df["type_rank"] = (
        df.groupby("opportunity_type")["priority_score"]
        .rank(method="first", ascending=False)
        .astype(int)
    )

    # Operational ordering: priority first, then detector score, then type.
    df = df.sort_values(
        ["priority_score", "score", "opportunity_type"],
        ascending=[False, False, True],
    ).reset_index(drop=True)

    # Keep evidence JSON and useful operational columns first.
    front = [
        "global_rank",
        "type_rank",
        "opportunity_id",
        "outlet_id",
        "opportunity_type",
        "priority_score",
        "priority_band",
        "action_urgency",
        "score",
        "priority",
        "evidence",
        "recommended_action",
    ]
    remaining = [c for c in df.columns if c not in front]
    df = df[[c for c in front if c in df.columns] + remaining]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False)

    print("\n" + "=" * 78)
    print("PRIORITY DISTRIBUTION")
    print("=" * 78)
    print(df["priority_band"].value_counts().sort_index().to_string())

    print("\n" + "=" * 78)
    print("TYPE-LEVEL PRIORITY DISTRIBUTION")
    print("=" * 78)
    print(
        pd.crosstab(
            df["opportunity_type"],
            df["priority_band"],
            margins=True,
        ).to_string()
    )

    print("\n" + "=" * 78)
    print("TOP 20 ACTIONABLE OPPORTUNITIES")
    print("=" * 78)
    cols = [
        "global_rank",
        "outlet_id",
        "opportunity_type",
        "priority_score",
        "priority_band",
        "evidence",
    ]
    print(df[cols].head(20).to_string(index=False))

    print("\n" + "=" * 78)
    print("OUTPUT")
    print("=" * 78)
    print(OUT)
    print("\nV5 opportunity prioritization complete.")


if __name__ == "__main__":
    main()
