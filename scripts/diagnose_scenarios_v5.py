from pathlib import Path
import pandas as pd
import numpy as np


ROOT = Path(__file__).resolve().parents[1]

FEATURES = (
    ROOT
    / "data"
    / "processed_v5"
    / "outlet_features.csv"
)

GROUND_TRUTH = (
    ROOT
    / "data"
    / "generated_v5"
    / "scenario_ground_truth.csv"
)


def main():

    features = pd.read_csv(FEATURES)
    truth = pd.read_csv(GROUND_TRUTH)

    df = features.merge(
        truth,
        on="outlet_id",
        how="left",
    )

    print("=" * 80)
    print("SALESFORGE — V5 SCENARIO DIAGNOSTICS")
    print("=" * 80)

    # ============================================================
    # REVENUE DECLINE
    # ============================================================

    revenue = df[
        df["revenue_decline_scenario"] == 1
    ]

    print("\n" + "=" * 80)
    print("1. REVENUE DECLINE")
    print("=" * 80)

    checks = {
        "previous_revenue >= 1000":
            revenue["revenue_previous_30d"] >= 1000,

        "previous_orders > 0":
            revenue["orders_previous_30d"] > 0,

        "current_orders > 0":
            revenue["orders_30d"] > 0,

        "growth <= -30%":
            revenue["revenue_growth_30d"] <= -0.30,

        "gap >= 1000":
            revenue["revenue_gap_vs_previous_30d"] >= 1000,
    }

    for name, mask in checks.items():

        print(
            f"{name:<35}"
            f"{mask.sum():>4}/{len(revenue)}"
            f"  ({mask.mean() * 100:6.2f}%)"
        )

    print("\nRevenue statistics:")

    print(
        revenue[
            [
                "revenue_previous_30d",
                "revenue_30d",
                "revenue_growth_30d",
                "revenue_gap_vs_previous_30d",
                "orders_previous_30d",
                "orders_30d",
            ]
        ].describe().round(2)
    )

    # ============================================================
    # INACTIVE
    # ============================================================

    inactive = df[
        df["inactive_scenario"] == 1
    ]

    print("\n" + "=" * 80)
    print("2. INACTIVE OUTLET")
    print("=" * 80)

    checks = {
        "previous_revenue >= 1000":
            inactive["revenue_previous_30d"] >= 1000,

        "previous_orders > 0":
            inactive["orders_previous_30d"] > 0,

        "current_revenue == 0":
            inactive["revenue_30d"] == 0,

        "current_orders == 0":
            inactive["orders_30d"] == 0,

        "days_since_last_order >= 30":
            inactive["days_since_last_order"] >= 30,
    }

    for name, mask in checks.items():

        print(
            f"{name:<35}"
            f"{mask.sum():>4}/{len(inactive)}"
            f"  ({mask.mean() * 100:6.2f}%)"
        )

    print("\nInactive statistics:")

    print(
        inactive[
            [
                "revenue_previous_30d",
                "revenue_30d",
                "orders_previous_30d",
                "orders_30d",
                "days_since_last_order",
            ]
        ].describe().round(2)
    )

    # ============================================================
    # STOCK RISK
    # ============================================================

    stock = df[
        df["stock_risk_scenario"] == 1
    ]

    print("\n" + "=" * 80)
    print("3. STOCK RISK")
    print("=" * 80)

    checks = {
        "stockout_events >= 2":
            stock["stockout_events_90d"] >= 2,

        "stockout_events >= 3":
            stock["stockout_events_90d"] >= 3,

        "stockout_rate >= 5%":
            stock["stockout_rate_90d"] >= 0.05,

        "avg_closing_stock <= 1":
            stock["avg_closing_stock_90d"] <= 1,
    }

    for name, mask in checks.items():

        print(
            f"{name:<35}"
            f"{mask.sum():>4}/{len(stock)}"
            f"  ({mask.mean() * 100:6.2f}%)"
        )

    print("\nStock statistics:")

    print(
        stock[
            [
                "stockout_events_90d",
                "stockout_rate_90d",
                "avg_closing_stock_90d",
            ]
        ].describe().round(3)
    )

    # ============================================================
    # CROSS SELL
    # ============================================================

    cross_sell = df[
        df["cross_sell_scenario"] == 1
    ]

    print("\n" + "=" * 80)
    print("4. CROSS-SELL")
    print("=" * 80)

    print(
        f"Planted outlets: "
        f"{len(cross_sell)}"
    )

    print(
        f"With target category: "
        f"{cross_sell['cross_sell_category'].ne('').sum()}"
        f"/{len(cross_sell)}"
    )

    print(
        f"Missing target category: "
        f"{cross_sell['cross_sell_category'].eq('').sum()}"
        f"/{len(cross_sell)}"
    )

    print(
        "\nTop target categories:"
    )

    print(
        cross_sell[
            "cross_sell_category"
        ]
        .value_counts()
        .head(10)
    )

    # ============================================================
    # OVERLAP
    # ============================================================

    print("\n" + "=" * 80)
    print("5. SCENARIO OVERLAP")
    print("=" * 80)

    scenario_columns = [
        "revenue_decline_scenario",
        "inactive_scenario",
        "stock_risk_scenario",
        "cross_sell_scenario",
    ]

    df["scenario_count"] = df[
        scenario_columns
    ].sum(axis=1)

    print(
        "Outlets with exactly one scenario: "
        f"{(df['scenario_count'] == 1).sum()}"
    )

    print(
        "Outlets with multiple scenarios: "
        f"{(df['scenario_count'] > 1).sum()}"
    )

    print(
        "Outlets with no scenario: "
        f"{(df['scenario_count'] == 0).sum()}"
    )

    print("\nScenario combinations:")

    print(
        df[
            scenario_columns
        ]
        .value_counts()
        .head(15)
    )

    print("\n" + "=" * 80)
    print("DIAGNOSTICS COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()