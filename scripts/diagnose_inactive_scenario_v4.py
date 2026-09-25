from pathlib import Path
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

FEATURES = ROOT / "data" / "processed_v4" / "outlet_features.csv"
GROUND_TRUTH = ROOT / "data" / "generated_v4" / "scenario_ground_truth.csv"


features = pd.read_csv(FEATURES)
ground_truth = pd.read_csv(GROUND_TRUTH)


# ============================================================
# Identify planted inactive outlets
# ============================================================

inactive_gt = ground_truth[
    ground_truth["inactive_scenario"] == 1
].copy()


print("=" * 70)
print("PLANTED INACTIVE OUTLETS")
print("=" * 70)

print("Count:", len(inactive_gt))

print("\nGround-truth columns:")
print(inactive_gt.columns.tolist())

print("\nSample:")
print(inactive_gt.head())


# ============================================================
# Feature columns
# ============================================================

print("\nFeature columns:")
print(features.columns.tolist())


# ============================================================
# Merge planted inactive outlets with features
# ============================================================

merged = inactive_gt.merge(
    features,
    on="outlet_id",
    how="left",
)


print("\n" + "=" * 70)
print("INACTIVE OUTLETS — FEATURE DIAGNOSTIC")
print("=" * 70)


cols = [
    "outlet_id",
    "revenue_30d",
    "revenue_previous_30d",
    "orders_30d",
    "orders_previous_30d",
    "days_since_last_order",
    "productive_call_rate_30d",
]

available = [
    c for c in cols
    if c in merged.columns
]

print(
    merged[available]
    .describe()
    .to_string()
)


# ============================================================
# Check detector eligibility
# ============================================================

merged["passes_previous_revenue"] = (
    merged["revenue_previous_30d"] >= 1000
)

merged["passes_inactive_days_30"] = (
    merged["days_since_last_order"] >= 30
)

merged["passes_inactive_days_45"] = (
    merged["days_since_last_order"] >= 45
)

merged["passes_both_30"] = (
    merged["passes_previous_revenue"]
    & merged["passes_inactive_days_30"]
)

merged["passes_both_45"] = (
    merged["passes_previous_revenue"]
    & merged["passes_inactive_days_45"]
)


print("\n" + "=" * 70)
print("DETECTOR ELIGIBILITY")
print("=" * 70)

print(
    "Previous revenue >= 1000:",
    merged["passes_previous_revenue"].sum(),
    "/",
    len(merged),
)

print(
    "Days since order >= 30:",
    merged["passes_inactive_days_30"].sum(),
    "/",
    len(merged),
)

print(
    "Days since order >= 45:",
    merged["passes_inactive_days_45"].sum(),
    "/",
    len(merged),
)

print(
    "Pass BOTH conditions (30-day threshold):",
    merged["passes_both_30"].sum(),
    "/",
    len(merged),
)

print(
    "Pass BOTH conditions (45-day threshold):",
    merged["passes_both_45"].sum(),
    "/",
    len(merged),
)


# ============================================================
# Inspect individual planted inactive outlets
# ============================================================

print("\n" + "=" * 70)
print("SAMPLE PLANTED INACTIVE OUTLETS")
print("=" * 70)

sample_cols = [
    "outlet_id",
    "revenue_30d",
    "revenue_previous_30d",
    "orders_30d",
    "orders_previous_30d",
    "days_since_last_order",
    "productive_call_rate_30d",
]

sample_cols = [
    c for c in sample_cols
    if c in merged.columns
]

print(
    merged[
        sample_cols
    ]
    .head(20)
    .to_string(index=False)
)


# ============================================================
# Final benchmark sanity checks
# ============================================================

print("\n" + "=" * 70)
print("BENCHMARK SANITY CHECK")
print("=" * 70)

print(
    "Revenue 30d == 0:",
    (
        merged["revenue_30d"] == 0
    ).sum(),
    "/",
    len(merged),
)

print(
    "Orders 30d == 0:",
    (
        merged["orders_30d"] == 0
    ).sum(),
    "/",
    len(merged),
)

print(
    "Previous revenue > 0:",
    (
        merged["revenue_previous_30d"] > 0
    ).sum(),
    "/",
    len(merged),
)

print(
    "Previous orders > 0:",
    (
        merged["orders_previous_30d"] > 0
    ).sum(),
    "/",
    len(merged),
)

print(
    "Days since order >= 30:",
    (
        merged["days_since_last_order"] >= 30
    ).sum(),
    "/",
    len(merged),
)

print(
    "Days since order >= 45:",
    (
        merged["days_since_last_order"] >= 45
    ).sum(),
    "/",
    len(merged),
)


print("\nDiagnostic complete.")