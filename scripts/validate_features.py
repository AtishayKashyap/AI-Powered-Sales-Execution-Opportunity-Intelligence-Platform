from pathlib import Path
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

FEATURES = ROOT / "data" / "processed" / "outlet_features.csv"
GROUND_TRUTH = ROOT / "data" / "generated" / "scenario_ground_truth.csv"


def compare(df, scenario_col, features):
    scenario = df[df[scenario_col] == 1]
    normal = df[df[scenario_col] == 0]

    print("\n" + "=" * 70)
    print(scenario_col)
    print("=" * 70)

    print(f"Scenario outlets : {len(scenario):,}")
    print(f"Normal outlets   : {len(normal):,}")

    rows = []

    for feature in features:
        scenario_mean = scenario[feature].mean()
        normal_mean = normal[feature].mean()

        scenario_median = scenario[feature].median()
        normal_median = normal[feature].median()

        rows.append(
            {
                "feature": feature,
                "scenario_mean": scenario_mean,
                "normal_mean": normal_mean,
                "scenario_median": scenario_median,
                "normal_median": normal_median,
            }
        )

    result = pd.DataFrame(rows)

    print(
        result.to_string(
            index=False,
            float_format=lambda x: f"{x:,.4f}",
        )
    )

    return result


def main():

    print("=" * 70)
    print("SALESFORGE — FEATURE VALIDATION")
    print("=" * 70)

    features = pd.read_csv(FEATURES)
    truth = pd.read_csv(GROUND_TRUTH)

    print(f"Feature rows: {len(features):,}")
    print(f"Truth rows  : {len(truth):,}")

    # ---------------------------------------------------------------
    # Merge ground truth with features
    # ---------------------------------------------------------------
    df = features.merge(
        truth,
        on="outlet_id",
        how="left",
    )

    # ---------------------------------------------------------------
    # Revenue decline
    # ---------------------------------------------------------------
    compare(
        df,
        "revenue_decline_scenario",
        [
            "revenue_30d",
            "revenue_previous_30d",
            "revenue_growth_30d",
            "revenue_gap_vs_previous_30d",
            "orders_30d",
            "orders_previous_30d",
            "order_frequency_growth_30d",
            "days_since_last_order",
            "target_achievement_pct",
        ],
    )

    # ---------------------------------------------------------------
    # Inactive outlet
    # ---------------------------------------------------------------
    compare(
        df,
        "inactive_scenario",
        [
            "revenue_30d",
            "orders_30d",
            "days_since_last_order",
            "visits_30d",
            "productive_call_rate_30d",
            "target_achievement_pct",
        ],
    )

    # ---------------------------------------------------------------
    # Stock risk
    # ---------------------------------------------------------------
    compare(
        df,
        "stock_risk_scenario",
        [
            "stockout_rate_90d",
            "stockout_events_90d",
            "avg_closing_stock_90d",
            "revenue_30d",
            "days_since_last_order",
        ],
    )

    # ---------------------------------------------------------------
    # Ground-truth counts
    # ---------------------------------------------------------------
    print("\n" + "=" * 70)
    print("GROUND-TRUTH COUNTS")
    print("=" * 70)

    scenario_columns = [
        "revenue_decline_scenario",
        "inactive_scenario",
        "cross_sell_scenario",
        "stock_risk_scenario",
    ]

    for col in scenario_columns:
        if col in df.columns:
            print(
                f"{col:<30} "
                f"{int(df[col].sum()):,}"
            )

    print("\nValidation complete.")


if __name__ == "__main__":
    main()