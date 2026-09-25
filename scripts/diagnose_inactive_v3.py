from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

FEATURES = ROOT / "data" / "processed_v2" / "outlet_features.csv"
GROUND_TRUTH = ROOT / "data" / "generated_v2" / "scenario_ground_truth.csv"
OPPORTUNITIES = ROOT / "data" / "processed_v2" / "opportunities_v3.csv"

features = pd.read_csv(FEATURES)
ground_truth = pd.read_csv(GROUND_TRUTH)
opportunities = pd.read_csv(OPPORTUNITIES)

# ---------------------------------------------------------
# Identify planted inactive outlets
# ---------------------------------------------------------

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


# ---------------------------------------------------------
# Determine outlet ID column
# ---------------------------------------------------------

print("\nFeature columns:")
print(features.columns.tolist())

print("\nOpportunity columns:")
print(opportunities.columns.tolist())


# ---------------------------------------------------------
# Merge planted inactive outlets with features
# ---------------------------------------------------------

merged = inactive_gt.merge(
    features,
    on="outlet_id",
    how="left"
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

available = [c for c in cols if c in merged.columns]

print(
    merged[available]
    .describe()
    .to_string()
)


# ---------------------------------------------------------
# Check detector eligibility
# ---------------------------------------------------------

merged["passes_previous_revenue"] = (
    merged["revenue_previous_30d"] >= 1000
)

merged["passes_inactive_days"] = (
    merged["days_since_last_order"] >= 45
)

merged["passes_both"] = (
    merged["passes_previous_revenue"]
    & merged["passes_inactive_days"]
)

print("\n" + "=" * 70)
print("DETECTOR ELIGIBILITY")
print("=" * 70)

print(
    "Previous revenue >= 1000:",
    merged["passes_previous_revenue"].sum(),
    "/",
    len(merged)
)

print(
    "Days since order >= 45:",
    merged["passes_inactive_days"].sum(),
    "/",
    len(merged)
)

print(
    "Pass BOTH conditions:",
    merged["passes_both"].sum(),
    "/",
    len(merged)
)


# ---------------------------------------------------------
# Compare with actual detected inactive outlets
# ---------------------------------------------------------

detected_inactive = opportunities[
    opportunities["opportunity_type"] == "INACTIVE_OUTLET"
]

print("\n" + "=" * 70)
print("DETECTED INACTIVE OPPORTUNITIES")
print("=" * 70)

print("Detected:", len(detected_inactive))

print(
    "Overlap with planted:",
    len(
        set(detected_inactive["outlet_id"])
        & set(inactive_gt["outlet_id"])
    )
)

print("\nDetected sample:")
print(
    detected_inactive[
        [c for c in [
            "outlet_id",
            "score",
            "priority",
            "days_since_last_order",
            "revenue_previous_30d"
        ] if c in detected_inactive.columns]
    ].head(20).to_string(index=False)
)

print("\nDiagnostic complete.")