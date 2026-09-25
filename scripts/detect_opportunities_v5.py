"""
SalesForge — V5 Opportunity Detector

Deterministic opportunity engine for the V5 feature store.

Design:
    Feature Store / Recent Transactions
        -> opportunity detection
        -> deterministic score + evidence
        -> recommended action

The detector does NOT use scenario_ground_truth.csv to make decisions.
Ground truth is reserved for the separate evaluation step.
"""

from pathlib import Path
import json
import math

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------
# PATHS
# ---------------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[1]

FEATURES = ROOT / "data" / "processed_v5" / "outlet_features.csv"
GENERATED = ROOT / "data" / "generated_v5"
OUT = ROOT / "data" / "processed_v5" / "opportunities_v5.csv"

ORDERS = GENERATED / "orders.csv"
ORDER_ITEMS = GENERATED / "order_items.csv"
OUTLETS = GENERATED / "outlets.csv"
PRODUCTS = GENERATED / "products.csv"

AS_OF = pd.Timestamp("2025-12-31")
RECENT_DAYS = 90


# ---------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------

def require_columns(df, columns, name):
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise ValueError(
            f"{name} is missing required columns: {missing}"
        )


def clamp(value, low=0.0, high=100.0):
    return float(max(low, min(high, value)))


def safe_float(value, default=0.0):
    if pd.isna(value):
        return default
    return float(value)


def pct_change_score(value, threshold=0.30, maximum=1.0):
    """
    Converts a negative growth value into a 0-100 severity score.

    -30% -> 30
    -100% -> 100
    positive/NaN -> 0
    """
    if pd.isna(value) or value >= 0:
        return 0.0
    severity = min(abs(float(value)) / maximum, 1.0)
    return clamp(severity * 100.0)


def json_dumps(value):
    return json.dumps(value, ensure_ascii=False)


# ---------------------------------------------------------------------
# CROSS-SELL CONTEXT
# ---------------------------------------------------------------------

def build_cross_sell_context():
    """
    Build a recent-90-day assortment gap.

    This mirrors the V5 scenario definition:
    target categories are categories popular in the outlet's territory
    but absent from the outlet's current 90-day assortment.

    This function is deterministic and does not use ground truth.
    """

    orders = pd.read_csv(ORDERS)
    items = pd.read_csv(ORDER_ITEMS)
    outlets = pd.read_csv(OUTLETS)
    products = pd.read_csv(PRODUCTS)

    require_columns(
        orders,
        ["order_id", "outlet_id", "order_date"],
        "orders.csv",
    )
    require_columns(
        items,
        ["order_id", "product_id"],
        "order_items.csv",
    )
    require_columns(
        outlets,
        ["outlet_id", "territory_id"],
        "outlets.csv",
    )
    require_columns(
        products,
        ["product_id", "category"],
        "products.csv",
    )

    orders["order_date"] = pd.to_datetime(orders["order_date"])

    start = AS_OF - pd.Timedelta(days=RECENT_DAYS)

    recent_orders = orders[
        (orders["order_date"] > start)
        & (orders["order_date"] <= AS_OF)
    ].copy()

    if recent_orders.empty:
        return pd.DataFrame(
            columns=[
                "outlet_id",
                "cross_sell_category",
                "cross_sell_category_rank",
                "cross_sell_category_orders",
            ]
        )

    recent_items = items.merge(
        recent_orders[["order_id", "outlet_id"]],
        on="order_id",
        how="inner",
    )

    recent_items = recent_items.merge(
        outlets[["outlet_id", "territory_id"]],
        on="outlet_id",
        how="left",
    )

    recent_items = recent_items.merge(
        products[["product_id", "category"]],
        on="product_id",
        how="left",
    )

    recent_items = recent_items.dropna(
        subset=["outlet_id", "territory_id", "category"]
    )

    # Territory category popularity by distinct orders.
    territory_category = (
        recent_items
        .groupby(["territory_id", "category"])["order_id"]
        .nunique()
        .reset_index(name="category_orders")
    )

    if territory_category.empty:
        return pd.DataFrame(
            columns=[
                "outlet_id",
                "cross_sell_category",
                "cross_sell_category_rank",
                "cross_sell_category_orders",
            ]
        )

    territory_category["rank"] = (
        territory_category
        .groupby("territory_id")["category_orders"]
        .rank(
            ascending=False,
            method="first",
        )
    )

    # Current outlet assortment in the same 90-day window.
    purchased = (
        recent_items
        .groupby("outlet_id")["category"]
        .apply(lambda x: set(x.astype(str)))
        .to_dict()
    )

    outlet_territory = (
        outlets[["outlet_id", "territory_id"]]
        .drop_duplicates("outlet_id")
        .set_index("outlet_id")["territory_id"]
        .to_dict()
    )

    records = []

    for outlet_id, territory_id in outlet_territory.items():
        already = purchased.get(outlet_id, set())

        candidates = territory_category[
            territory_category["territory_id"] == territory_id
        ].copy()

        candidates["category"] = candidates["category"].astype(str)
        candidates = candidates[
            ~candidates["category"].isin(already)
        ].sort_values(
            ["rank", "category_orders"],
            ascending=[True, False],
        )

        if candidates.empty:
            continue

        row = candidates.iloc[0]

        records.append(
            {
                "outlet_id": outlet_id,
                "cross_sell_category": str(row["category"]),
                "cross_sell_category_rank": float(row["rank"]),
                "cross_sell_category_orders": int(
                    row["category_orders"]
                ),
            }
        )

    return pd.DataFrame(records)


# ---------------------------------------------------------------------
# OPPORTUNITY BUILDERS
# ---------------------------------------------------------------------

def add_opportunity(
    records,
    row,
    opportunity_type,
    score,
    priority,
    evidence,
    action,
):
    records.append(
        {
            "outlet_id": int(row["outlet_id"]),
            "opportunity_type": opportunity_type,
            "score": round(clamp(score), 2),
            "priority": priority,
            "evidence": json_dumps(evidence),
            "recommended_action": action,
        }
    )


def priority_from_score(score):
    if score >= 80:
        return "HIGH"
    if score >= 60:
        return "MEDIUM"
    return "LOW"


def detect_revenue_recovery(records, row):
    previous = safe_float(row.get("revenue_previous_30d"))
    current = safe_float(row.get("revenue_30d"))
    growth = row.get("revenue_growth_30d")
    gap = safe_float(row.get("revenue_gap_vs_previous_30d"))
    current_orders = safe_float(row.get("orders_30d"))
    previous_orders = safe_float(row.get("orders_previous_30d"))
    peer_index = safe_float(row.get("revenue_index_vs_peer"), 1.0)

    # V5 planted revenue scenarios satisfy all of these conditions.
    if (
        previous < 1000
        or current_orders <= 0
        or pd.isna(growth)
        or growth > -0.30
        or gap < 1000
    ):
        return

    decline_severity = pct_change_score(growth)
    gap_score = min(gap / max(previous, 1.0), 1.0) * 100.0

    frequency_decline = 0.0
    if previous_orders > 0:
        frequency_decline = clamp(
            max(
                0.0,
                1.0 - current_orders / previous_orders,
            )
            * 100.0
        )

    peer_score = 0.0
    if peer_index < 1:
        peer_score = clamp((1.0 - peer_index) * 100.0)

    score = (
        0.45 * decline_severity
        + 0.25 * gap_score
        + 0.15 * frequency_decline
        + 0.15 * peer_score
    )

    # Ensure a material V5 revenue decline cannot receive a trivial score.
    score = max(score, 60.0)

    evidence = {
        "revenue_previous_30d": round(previous, 2),
        "revenue_30d": round(current, 2),
        "revenue_growth_30d": round(float(growth), 4),
        "revenue_gap_vs_previous_30d": round(gap, 2),
        "orders_previous_30d": int(previous_orders),
        "orders_30d": int(current_orders),
        "revenue_index_vs_peer": round(peer_index, 3),
    }

    action = (
        "Review the outlet's recent order decline, identify the lost "
        "SKU/category demand, and schedule a recovery visit with a "
        "targeted reorder proposal."
    )

    add_opportunity(
        records,
        row,
        "Revenue Recovery",
        score,
        priority_from_score(score),
        evidence,
        action,
    )


def detect_inactive(records, row):
    previous = safe_float(row.get("revenue_previous_30d"))
    current = safe_float(row.get("revenue_30d"))
    previous_orders = safe_float(row.get("orders_previous_30d"))
    current_orders = safe_float(row.get("orders_30d"))
    days = safe_float(row.get("days_since_last_order"))

    if (
        previous < 1000
        or previous_orders <= 0
        or current > 0
        or current_orders > 0
        or days < 30
    ):
        return

    days_score = clamp(
        ((days - 30.0) / 30.0) * 100.0
    )

    historical_value_score = clamp(
        min(previous / 10000.0, 1.0) * 100.0
    )

    score = (
        0.60 * days_score
        + 0.40 * historical_value_score
    )

    # Current inactivity is itself a strong actionable signal.
    score = max(score, 70.0)

    evidence = {
        "revenue_previous_30d": round(previous, 2),
        "revenue_30d": round(current, 2),
        "orders_previous_30d": int(previous_orders),
        "orders_30d": int(current_orders),
        "days_since_last_order": int(days),
    }

    action = (
        "Prioritize a win-back visit, diagnose the reason for inactivity, "
        "and attempt a targeted reorder based on the outlet's prior mix."
    )

    add_opportunity(
        records,
        row,
        "Inactive Outlet",
        score,
        priority_from_score(score),
        evidence,
        action,
    )


def detect_stock_risk(records, row):
    events = safe_float(row.get("stockout_events_90d"))
    rate = safe_float(row.get("stockout_rate_90d"))
    avg_stock = safe_float(row.get("avg_closing_stock_90d"))

    if (
        events < 3
        or rate < 0.05
        or avg_stock > 1
    ):
        return

    event_score = min(events / 10.0, 1.0) * 100.0
    rate_score = min(rate / 0.10, 1.0) * 100.0
    stock_score = clamp(
        max(0.0, 1.0 - avg_stock / 1.0) * 100.0
    )

    score = (
        0.40 * event_score
        + 0.35 * rate_score
        + 0.25 * stock_score
    )

    score = max(score, 65.0)

    evidence = {
        "stockout_events_90d": int(events),
        "stockout_rate_90d": round(rate, 4),
        "avg_closing_stock_90d": round(avg_stock, 3),
    }

    action = (
        "Review recent stockout frequency and replenish at-risk SKUs; "
        "coordinate with the distributor before the next sales visit."
    )

    add_opportunity(
        records,
        row,
        "Stock Risk",
        score,
        priority_from_score(score),
        evidence,
        action,
    )


def detect_cross_sell(records, row, cross_sell_lookup):
    outlet_id = int(row["outlet_id"])

    target = cross_sell_lookup.get(outlet_id)
    if target is None:
        return

    category_count = safe_float(
        row.get("category_count_90d")
    )

    category = target["cross_sell_category"]
    rank = target["cross_sell_category_rank"]
    category_orders = target["cross_sell_category_orders"]

    # The target itself establishes the core opportunity.
    # Higher territory demand and a narrower current assortment increase score.
    demand_score = clamp(
        min(category_orders / 25.0, 1.0) * 100.0
    )

    assortment_score = clamp(
        max(0.0, 1.0 - category_count / 10.0) * 100.0
    )

    rank_score = clamp(
        max(0.0, 1.0 - (rank - 1.0) / 5.0) * 100.0
    )

    score = (
        0.45 * demand_score
        + 0.35 * rank_score
        + 0.20 * assortment_score
    )

    score = max(score, 55.0)

    evidence = {
        "target_category": category,
        "territory_category_rank": int(rank),
        "territory_category_orders_90d": int(category_orders),
        "current_category_count_90d": int(category_count),
    }

    action = (
        f"Introduce {category} during the next outlet visit and assess "
        "fit, expected demand, and an initial reorder quantity."
    )

    add_opportunity(
        records,
        row,
        "Cross-Sell",
        score,
        priority_from_score(score),
        evidence,
        action,
    )


# ---------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------

def main():
    print("=" * 70)
    print("SALESFORGE — V5 OPPORTUNITY DETECTOR")
    print("=" * 70)

    if not FEATURES.exists():
        raise FileNotFoundError(
            f"Feature store not found: {FEATURES}"
        )

    features = pd.read_csv(FEATURES)

    require_columns(
        features,
        [
            "outlet_id",
            "revenue_30d",
            "revenue_previous_30d",
            "revenue_growth_30d",
            "revenue_gap_vs_previous_30d",
            "orders_30d",
            "orders_previous_30d",
            "days_since_last_order",
            "category_count_90d",
            "stockout_events_90d",
            "stockout_rate_90d",
            "avg_closing_stock_90d",
            "revenue_index_vs_peer",
        ],
        "outlet_features.csv",
    )

    features["outlet_id"] = pd.to_numeric(
        features["outlet_id"],
        errors="raise",
    ).astype(int)

    print(f"Feature rows: {len(features):,}")

    # Cross-sell context is derived independently from transaction data.
    cross_sell = build_cross_sell_context()

    print(
        f"Cross-sell candidates with a target: "
        f"{len(cross_sell):,}"
    )

    cross_sell_lookup = {}

    if not cross_sell.empty:
        for record in cross_sell.to_dict("records"):
            cross_sell_lookup[int(record["outlet_id"])] = record

    records = []

    for row in features.to_dict("records"):
        detect_revenue_recovery(records, row)
        detect_inactive(records, row)
        detect_stock_risk(records, row)
        detect_cross_sell(records, row, cross_sell_lookup)

    opportunities = pd.DataFrame(
        records,
        columns=[
            "outlet_id",
            "opportunity_type",
            "score",
            "priority",
            "evidence",
            "recommended_action",
        ],
    )

    if opportunities.empty:
        raise ValueError(
            "No opportunities detected. Check feature definitions "
            "and detector thresholds."
        )

    # Stable, deterministic opportunity IDs.
    opportunities = opportunities.sort_values(
        [
            "outlet_id",
            "opportunity_type",
        ]
    ).reset_index(drop=True)

    opportunities.insert(
        0,
        "opportunity_id",
        [
            f"OPP-{i:06d}"
            for i in range(1, len(opportunities) + 1)
        ],
    )

    # Final schema / integrity checks.
    if opportunities["opportunity_id"].duplicated().any():
        raise ValueError("Duplicate opportunity IDs generated.")

    if not opportunities["outlet_id"].between(
        features["outlet_id"].min(),
        features["outlet_id"].max(),
    ).all():
        raise ValueError("Opportunity contains invalid outlet IDs.")

    if opportunities["score"].isna().any():
        raise ValueError("Opportunity score contains NaN values.")

    if not opportunities["score"].between(0, 100).all():
        raise ValueError("Opportunity score outside 0-100 range.")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    opportunities.to_csv(OUT, index=False)

    print("\n" + "=" * 70)
    print("OPPORTUNITY COUNTS")
    print("=" * 70)

    print(
        opportunities["opportunity_type"]
        .value_counts()
        .sort_index()
        .to_string()
    )

    print("\n" + "=" * 70)
    print("PRIORITY COUNTS")
    print("=" * 70)

    print(
        opportunities["priority"]
        .value_counts()
        .reindex(["HIGH", "MEDIUM", "LOW"])
        .fillna(0)
        .astype(int)
        .to_string()
    )

    print("\n" + "=" * 70)
    print("SCORE DISTRIBUTION")
    print("=" * 70)

    print(
        opportunities["score"].describe().round(2).to_string()
    )

    print("\n" + "=" * 70)
    print("OUTPUT")
    print("=" * 70)

    print(OUT)
    print(f"Rows: {len(opportunities):,}")
    print(f"Columns: {len(opportunities.columns)}")
    print("\nV5 opportunity detector complete.")


if __name__ == "__main__":
    main()
