from pathlib import Path
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

FEATURES = (
    ROOT
    / "data"
    / "processed_v4"
    / "outlet_features.csv"
)

GROUND_TRUTH = (
    ROOT
    / "data"
    / "generated_v4"
    / "scenario_ground_truth.csv"
)

OPPORTUNITIES = (
    ROOT
    / "data"
    / "processed_v4"
    / "opportunities_v4.csv"
)


features = pd.read_csv(FEATURES)
ground_truth = pd.read_csv(GROUND_TRUTH)
opportunities = pd.read_csv(OPPORTUNITIES)


# ============================================================
# Merge features with ground truth
# ============================================================

data = ground_truth.merge(
    features,
    on="outlet_id",
    how="left",
)


# ============================================================
# REVENUE DECLINE DIAGNOSTIC
# ============================================================

revenue = data[
    data["revenue_decline_scenario"] == 1
].copy()

revenue["passes_previous_revenue"] = (
    revenue["revenue_previous_30d"] >= 1000
)

revenue["passes_growth"] = (
    revenue["revenue_growth_30d"] <= -0.30
)

revenue["passes_gap"] = (
    revenue["revenue_gap_vs_previous_30d"] >= 1000
)

revenue["passes_current_orders"] = (
    revenue["orders_30d"] > 0
)

revenue["passes_detector"] = (
    revenue["passes_previous_revenue"]
    & revenue["passes_growth"]
    & revenue["passes_gap"]
    & revenue["passes_current_orders"]
)


print("=" * 70)
print("SALESFORGE — V4 OPPORTUNITY DIAGNOSTIC")
print("=" * 70)

print("\n" + "=" * 70)
print("REVENUE RECOVERY — PLANTED CASES")
print("=" * 70)

print(
    "Planted revenue-decline outlets:",
    len(revenue),
)

print(
    "Previous revenue >= 1000:",
    revenue["passes_previous_revenue"].sum(),
    "/",
    len(revenue),
)

print(
    "Growth <= -30%:",
    revenue["passes_growth"].sum(),
    "/",
    len(revenue),
)

print(
    "Revenue gap >= 1000:",
    revenue["passes_gap"].sum(),
    "/",
    len(revenue),
)

print(
    "Current orders > 0:",
    revenue["passes_current_orders"].sum(),
    "/",
    len(revenue),
)

print(
    "Pass ALL detector conditions:",
    revenue["passes_detector"].sum(),
    "/",
    len(revenue),
)


print("\nRevenue-decline feature statistics:")

print(
    revenue[
        [
            "revenue_30d",
            "revenue_previous_30d",
            "revenue_growth_30d",
            "revenue_gap_vs_previous_30d",
            "orders_30d",
            "orders_previous_30d",
            "order_frequency_growth_30d",
            "revenue_growth_gap_vs_peer",
        ]
    ]
    .describe()
    .to_string()
)


# ============================================================
# INACTIVE DIAGNOSTIC
# ============================================================

inactive = data[
    data["inactive_scenario"] == 1
].copy()

inactive["passes_previous_revenue"] = (
    inactive["revenue_previous_30d"] >= 1000
)

inactive["passes_days"] = (
    inactive["days_since_last_order"] >= 30
)

inactive["passes_detector"] = (
    inactive["passes_previous_revenue"]
    & inactive["passes_days"]
)


print("\n" + "=" * 70)
print("INACTIVE OUTLET — PLANTED CASES")
print("=" * 70)

print(
    "Planted inactive outlets:",
    len(inactive),
)

print(
    "Previous revenue >= 1000:",
    inactive["passes_previous_revenue"].sum(),
    "/",
    len(inactive),
)

print(
    "Days inactive >= 30:",
    inactive["passes_days"].sum(),
    "/",
    len(inactive),
)

print(
    "Pass detector conditions:",
    inactive["passes_detector"].sum(),
    "/",
    len(inactive),
)


# ============================================================
# STOCK RISK DIAGNOSTIC
# ============================================================

stock = data[
    data["stock_risk_scenario"] == 1
].copy()

stock["passes_events"] = (
    stock["stockout_events_90d"] >= 2
)

stock["passes_rate"] = (
    stock["stockout_rate_90d"] >= 0.05
)

stock["passes_low_stock"] = (
    stock["avg_closing_stock_90d"] <= 1
)


print("\n" + "=" * 70)
print("STOCK RISK — PLANTED CASES")
print("=" * 70)

print(
    "Planted stock-risk outlets:",
    len(stock),
)

print(
    "Stockout events >= 2:",
    stock["passes_events"].sum(),
    "/",
    len(stock),
)

print(
    "Stockout rate >= 5%:",
    stock["passes_rate"].sum(),
    "/",
    len(stock),
)

print(
    "Average closing stock <= 1:",
    stock["passes_low_stock"].sum(),
    "/",
    len(stock),
)


print("\nStock-risk feature statistics:")

print(
    stock[
        [
            "stockout_events_90d",
            "stockout_rate_90d",
            "avg_closing_stock_90d",
            "revenue_30d",
            "days_since_last_order",
        ]
    ]
    .describe()
    .to_string()
)


# ============================================================
# DETECTED VS PLANTED OVERLAP
# ============================================================

print("\n" + "=" * 70)
print("ACTUAL DETECTOR OVERLAP")
print("=" * 70)

for opportunity_type, scenario_column in [
    (
        "REVENUE_RECOVERY",
        "revenue_decline_scenario",
    ),
    (
        "INACTIVE_OUTLET",
        "inactive_scenario",
    ),
    (
        "STOCK_RISK",
        "stock_risk_scenario",
    ),
]:

    detected_ids = set(
        opportunities.loc[
            opportunities["opportunity_type"]
            == opportunity_type,
            "outlet_id",
        ]
    )

    planted_ids = set(
        ground_truth.loc[
            ground_truth[scenario_column] == 1,
            "outlet_id",
        ]
    )

    overlap = detected_ids & planted_ids

    print(
        f"\n{opportunity_type}"
    )

    print(
        "Detected:",
        len(detected_ids),
    )

    print(
        "Planted:",
        len(planted_ids),
    )

    print(
        "Overlap:",
        len(overlap),
    )


print("\nDiagnostic complete.")