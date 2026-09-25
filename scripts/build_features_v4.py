from pathlib import Path
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "generated_v4"
OUT = ROOT / "data" / "processed_v4"

OUT.mkdir(parents=True, exist_ok=True)


def load(name):
    return pd.read_csv(DATA / name)


def main():
    print("=" * 70)
    print("SALESFORGE — OUTLET FEATURE STORE")
    print("=" * 70)

    # ------------------------------------------------------------------
    # Load
    # ------------------------------------------------------------------
    outlets = load("outlets.csv")
    orders = load("orders.csv")
    order_items = load("order_items.csv")
    products = load("products.csv")
    visits = load("visits.csv")
    inventory = load("inventory_snapshots.csv")
    targets = load("targets.csv")

    # Dates
    orders["order_date"] = pd.to_datetime(orders["order_date"])
    order_items = order_items.merge(
        orders[["order_id", "outlet_id", "order_date"]],
        on="order_id",
        how="left",
    )

    visits["visit_date"] = pd.to_datetime(visits["visit_date"])
    inventory["snapshot_date"] = pd.to_datetime(inventory["snapshot_date"])
    targets["target_month"] = pd.to_datetime(targets["target_month"])

    # Use the latest order date as the feature-store "as of" date.
    as_of = orders["order_date"].max()

    print(f"As-of date: {as_of.date()}")
    print(f"Outlets: {len(outlets):,}")

    # ------------------------------------------------------------------
    # Base outlet table
    # ------------------------------------------------------------------
    features = outlets[
        [
            "outlet_id",
            "outlet_name",
            "outlet_type",
            "territory_id",
            "distributor_id",
            "rep_id",
            "city",
            "tier",
        ]
    ].copy()

    # ------------------------------------------------------------------
    # 1. ORDER / REVENUE FEATURES
    # ------------------------------------------------------------------
    current_30_start = as_of - pd.Timedelta(days=30)
    previous_30_start = as_of - pd.Timedelta(days=60)
    current_90_start = as_of - pd.Timedelta(days=90)

    current_30 = orders[
        (orders["order_date"] > current_30_start)
        & (orders["order_date"] <= as_of)
    ]

    previous_30 = orders[
        (orders["order_date"] > previous_30_start)
        & (orders["order_date"] <= current_30_start)
    ]

    current_90 = orders[
        (orders["order_date"] > current_90_start)
        & (orders["order_date"] <= as_of)
    ]

    # Current 30-day revenue/order metrics
    order_30_features = (
        current_30.groupby("outlet_id")
        .agg(
            revenue_30d=("net_value", "sum"),
            orders_30d=("order_id", "nunique"),
            avg_order_value_30d=("net_value", "mean"),
        )
        .reset_index()
    )

    # Previous 30-day metrics
    previous_30_features = (
        previous_30.groupby("outlet_id")
        .agg(
            revenue_previous_30d=("net_value", "sum"),
            orders_previous_30d=("order_id", "nunique"),
        )
        .reset_index()
    )

    features = features.merge(order_30_features, on="outlet_id", how="left")
    features = features.merge(
        previous_30_features,
        on="outlet_id",
        how="left",
    )

    numeric_cols = [
        "revenue_30d",
        "orders_30d",
        "avg_order_value_30d",
        "revenue_previous_30d",
        "orders_previous_30d",
    ]

    for col in numeric_cols:
        features[col] = features[col].fillna(0)

    # Growth metrics
    features["revenue_growth_30d"] = np.where(
        features["revenue_previous_30d"] > 0,
        (
            features["revenue_30d"]
            - features["revenue_previous_30d"]
        )
        / features["revenue_previous_30d"],
        np.nan,
    )

    features["order_frequency_growth_30d"] = np.where(
        features["orders_previous_30d"] > 0,
        (
            features["orders_30d"]
            - features["orders_previous_30d"]
        )
        / features["orders_previous_30d"],
        np.nan,
    )

    features["revenue_gap_vs_previous_30d"] = (
        features["revenue_previous_30d"]
        - features["revenue_30d"]
    )

    features["order_frequency_gap"] = (
        features["orders_previous_30d"]
        - features["orders_30d"]
    )

    # ------------------------------------------------------------------
    # 2. RECENCY
    # ------------------------------------------------------------------
    last_order = (
        orders.groupby("outlet_id")["order_date"]
        .max()
        .reset_index(name="last_order_date")
    )

    features = features.merge(last_order, on="outlet_id", how="left")

    features["days_since_last_order"] = (
        as_of - features["last_order_date"]
    ).dt.days

    # ------------------------------------------------------------------
    # 3. ASSORTMENT / PRODUCT FEATURES
    # ------------------------------------------------------------------
    items_90 = order_items[
        (order_items["order_date"] > current_90_start)
        & (order_items["order_date"] <= as_of)
    ].merge(
        products[
            [
                "product_id",
                "category",
                "subcategory",
            ]
        ],
        on="product_id",
        how="left",
    )

    assortment_features = (
        items_90.groupby("outlet_id")
        .agg(
            active_skus_90d=("product_id", "nunique"),
            category_count_90d=("category", "nunique"),
            subcategory_count_90d=("subcategory", "nunique"),
        )
        .reset_index()
    )

    features = features.merge(
        assortment_features,
        on="outlet_id",
        how="left",
    )

    for col in [
        "active_skus_90d",
        "category_count_90d",
        "subcategory_count_90d",
    ]:
        features[col] = features[col].fillna(0)

    # ------------------------------------------------------------------
    # 4. VISIT / REP PRODUCTIVITY FEATURES
    # ------------------------------------------------------------------
    visits_30 = visits[
        (visits["visit_date"] > current_30_start)
        & (visits["visit_date"] <= as_of)
    ]

    visit_features = (
        visits_30.groupby("outlet_id")
        .agg(
            visits_30d=("visit_id", "nunique"),
            productive_visits_30d=("productive_flag", "sum"),
            avg_visit_duration_30d=("duration_minutes", "mean"),
        )
        .reset_index()
    )

    features = features.merge(
        visit_features,
        on="outlet_id",
        how="left",
    )

    for col in [
        "visits_30d",
        "productive_visits_30d",
        "avg_visit_duration_30d",
    ]:
        features[col] = features[col].fillna(0)

    features["productive_call_rate_30d"] = np.where(
        features["visits_30d"] > 0,
        features["productive_visits_30d"]
        / features["visits_30d"],
        0,
    )

    features["visits_per_week_30d"] = (
        features["visits_30d"] / (30 / 7)
    )

    # ------------------------------------------------------------------
    # 5. INVENTORY / STOCK-RISK FEATURES
    # ------------------------------------------------------------------
    inventory_90 = inventory[
        (inventory["snapshot_date"] > current_90_start)
        & (inventory["snapshot_date"] <= as_of)
    ]

    inventory_features = (
        inventory_90.groupby("outlet_id")
        .agg(
            inventory_snapshots_90d=("snapshot_id", "count"),
            stockout_events_90d=("stockout_flag", "sum"),
            avg_closing_stock_90d=("closing_stock", "mean"),
        )
        .reset_index()
    )

    features = features.merge(
        inventory_features,
        on="outlet_id",
        how="left",
    )

    for col in [
        "inventory_snapshots_90d",
        "stockout_events_90d",
        "avg_closing_stock_90d",
    ]:
        features[col] = features[col].fillna(0)

    features["stockout_rate_90d"] = np.where(
        features["inventory_snapshots_90d"] > 0,
        features["stockout_events_90d"]
        / features["inventory_snapshots_90d"],
        0,
    )

    # ------------------------------------------------------------------
    # 6. TARGET ACHIEVEMENT
    # ------------------------------------------------------------------
    current_month = as_of.to_period("M")

    month_orders = orders[
        orders["order_date"].dt.to_period("M") == current_month
    ]

    month_revenue = (
        month_orders.groupby("outlet_id")["net_value"]
        .sum()
        .reset_index(name="current_month_revenue")
    )

    current_targets = targets[
        targets["target_month"].dt.to_period("M") == current_month
    ]

    month_targets = (
        current_targets.groupby("outlet_id")["revenue_target"]
        .sum()
        .reset_index(name="revenue_target")
    )

    features = features.merge(
        month_revenue,
        on="outlet_id",
        how="left",
    )

    features = features.merge(
        month_targets,
        on="outlet_id",
        how="left",
    )

    features["current_month_revenue"] = (
        features["current_month_revenue"].fillna(0)
    )

    features["revenue_target"] = (
        features["revenue_target"].fillna(0)
    )

    features["target_achievement_pct"] = np.where(
        features["revenue_target"] > 0,
        features["current_month_revenue"]
        / features["revenue_target"]
        * 100,
        np.nan,
    )

    # ------------------------------------------------------------------
    # 7. EFFICIENCY
    # ------------------------------------------------------------------
    features["revenue_per_visit_30d"] = np.where(
        features["visits_30d"] > 0,
        features["revenue_30d"]
        / features["visits_30d"],
        0,
    )

    # ------------------------------------------------------------------
    # 8. PEER BENCHMARKING
    # ------------------------------------------------------------------
    # Compare outlets against similar outlets:
    # same territory + same tier.
    features["peer_group"] = (
        features["territory_id"].astype(str)
        + "_"
        + features["tier"].astype(str)
    )

    peer_revenue_median = features.groupby(
        "peer_group"
    )["revenue_30d"].transform("median")

    peer_growth_median = features.groupby(
        "peer_group"
    )["revenue_growth_30d"].transform("median")

    features["peer_median_revenue_30d"] = peer_revenue_median

    features["revenue_index_vs_peer"] = np.where(
        peer_revenue_median > 0,
        features["revenue_30d"]
        / peer_revenue_median,
        np.nan,
    )

    features["revenue_growth_gap_vs_peer"] = (
        features["revenue_growth_30d"]
        - peer_growth_median
    )

    # ------------------------------------------------------------------
    # 9. BUSINESS FLAGS
    # ------------------------------------------------------------------
    features["inactive_30d_flag"] = (
        features["days_since_last_order"] > 30
    ).astype(int)

    features["declining_revenue_flag"] = (
        features["revenue_growth_30d"] < -0.15
    ).astype(int)

    features["high_stockout_flag"] = (
        features["stockout_rate_90d"] >= 0.10
    ).astype(int)

    features["under_target_flag"] = (
        features["target_achievement_pct"] < 80
    ).astype(int)

    # ------------------------------------------------------------------
    # 10. Clean numeric output
    # ------------------------------------------------------------------
    features = features.replace(
        [np.inf, -np.inf],
        np.nan,
    )

    # Keep dates readable.
    features["last_order_date"] = (
        features["last_order_date"]
        .dt.strftime("%Y-%m-%d")
    )

    output = OUT / "outlet_features.csv"

    features.to_csv(
        output,
        index=False,
    )

    print("\nFeature store created:")
    print(f"  {output}")
    print(f"  Rows: {len(features):,}")
    print(f"  Columns: {len(features.columns):,}")

    print("\nKey feature sample:")
    print(
        features[
            [
                "outlet_id",
                "revenue_30d",
                "revenue_growth_30d",
                "days_since_last_order",
                "active_skus_90d",
                "productive_call_rate_30d",
                "stockout_rate_90d",
                "target_achievement_pct",
                "revenue_index_vs_peer",
            ]
        ].head(10).to_string(index=False)
    )

    print("\nDone.")


if __name__ == "__main__":
    main()