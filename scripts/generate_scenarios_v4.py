from pathlib import Path
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

INPUT = ROOT / "data" / "generated"
OUTPUT = ROOT / "data" / "generated_v4"

SEED = 42
rng = np.random.default_rng(SEED)

OUTPUT.mkdir(parents=True, exist_ok=True)


def copy_base_data():
    """
    Copy the original generated dataset into generated_v3.

    Scenario modifications are then applied to this clean baseline.
    """

    files = [
        "territories.csv",
        "distributors.csv",
        "sales_reps.csv",
        "outlets.csv",
        "products.csv",
        "orders.csv",
        "order_items.csv",
        "visits.csv",
        "inventory_snapshots.csv",
        "targets.csv",
    ]

    for filename in files:
        source = INPUT / filename
        destination = OUTPUT / filename

        df = pd.read_csv(source)
        df.to_csv(destination, index=False)

        print(
            f"Copied {filename:<28} "
            f"{len(df):>10,} rows"
        )


def choose_scenarios(
    outlets,
    orders,
):
    """
    Select controlled, mostly non-overlapping scenario groups.

    Inactive outlets are selected only from outlets that demonstrate
    sufficient historical activity in the previous 30-day window.

    This prevents already-inactive outlets from being accidentally
    labelled as planted inactivity scenarios.
    """

    outlet_ids = outlets["outlet_id"].tolist()

    rng.shuffle(outlet_ids)

    # ------------------------------------------------------------
    # Determine as-of date from the baseline order history
    # ------------------------------------------------------------

    orders = orders.copy()

    orders["order_date"] = pd.to_datetime(
        orders["order_date"]
    )

    as_of = orders["order_date"].max()

    current_start = as_of - pd.Timedelta(days=30)
    previous_start = as_of - pd.Timedelta(days=60)

    # ------------------------------------------------------------
    # Calculate previous 30-day revenue for each outlet
    # ------------------------------------------------------------

    previous_orders = orders[
        (orders["order_date"] > previous_start)
        & (orders["order_date"] <= current_start)
    ]

    previous_revenue = (
        previous_orders
        .groupby("outlet_id")["net_value"]
        .sum()
    )

    # ------------------------------------------------------------
    # Eligible inactive outlets
    #
    # These outlets must have had meaningful historical revenue
    # before we artificially make them inactive.
    # ------------------------------------------------------------

    eligible_inactive = set(
        previous_revenue[
            previous_revenue >= 1000
        ].index
    )

    # Preserve deterministic shuffled ordering.
    eligible_inactive_ids = [
        outlet_id
        for outlet_id in outlet_ids
        if outlet_id in eligible_inactive
    ]

    if len(eligible_inactive_ids) < 100:
        raise ValueError(
            "Not enough eligible outlets for inactive scenario. "
            f"Required: 100, "
            f"Available: {len(eligible_inactive_ids)}"
        )

    inactive_ids = eligible_inactive_ids[:100]
    inactive_set = set(inactive_ids)

    # ------------------------------------------------------------
    # Select remaining scenarios from outlets that are not already
    # assigned to the inactive scenario.
    # ------------------------------------------------------------

    remaining_ids = [
        outlet_id
        for outlet_id in outlet_ids
        if outlet_id not in inactive_set
    ]

    decline_ids = remaining_ids[:120]

    decline_set = set(decline_ids)

    remaining_ids = [
        outlet_id
        for outlet_id in remaining_ids
        if outlet_id not in decline_set
    ]

    stock_ids = remaining_ids[:110]

    stock_set = set(stock_ids)

    remaining_ids = [
        outlet_id
        for outlet_id in remaining_ids
        if outlet_id not in stock_set
    ]

    cross_sell_ids = remaining_ids[:140]

    return {
        "revenue_decline_scenario": set(
            decline_ids
        ),
        "inactive_scenario": inactive_set,
        "stock_risk_scenario": stock_set,
        "cross_sell_scenario": set(
            cross_sell_ids
        ),
    }

def modify_revenue_decline(
    orders,
    order_items,
    scenario_ids,
):
    """
    Make current-period revenue materially lower for selected outlets.

    Recent orders are partially devalued and approximately 35% of
    recent orders are removed entirely.
    """

    orders["order_date"] = pd.to_datetime(
        orders["order_date"]
    )

    as_of = orders["order_date"].max()

    current_start = as_of - pd.Timedelta(days=30)

    mask = (
        orders["outlet_id"].isin(scenario_ids)
        & (orders["order_date"] > current_start)
        & (orders["order_date"] <= as_of)
    )

    current_orders = orders.loc[mask].copy()

    # Reduce recent order values.
    orders.loc[mask, "gross_value"] *= 0.45
    orders.loc[mask, "discount_value"] *= 0.45
    orders.loc[mask, "net_value"] *= 0.45

    # Randomly remove roughly 35% of recent orders.
    if len(current_orders) > 0:
        remove_ids = current_orders.sample(
            frac=0.35,
            random_state=SEED,
        )["order_id"]

        orders.drop(
            orders[
                orders["order_id"].isin(remove_ids)
            ].index,
            inplace=True,
        )

        # Remove corresponding order items.
        order_items.drop(
            order_items[
                order_items["order_id"].isin(remove_ids)
            ].index,
            inplace=True,
        )

    print(
        f"\nRevenue decline scenarios modified: "
        f"{len(scenario_ids):,}"
    )

    return orders, order_items


def modify_inactive(
    orders,
    order_items,
    visits,
    scenario_ids,
):
    """
    Force selected previously active outlets to become inactive.

    IMPORTANT:
    Only the most recent 30 days of orders are removed.

    This preserves the previous 30-day revenue window so the feature
    store can establish that the outlet was previously active.

    The resulting pattern is:

        Previous 30 days -> historical activity
        Recent 30 days   -> zero orders / zero revenue

    This makes the benchmark compatible with an inactivity detector.
    """

    orders["order_date"] = pd.to_datetime(
        orders["order_date"]
    )

    visits["visit_date"] = pd.to_datetime(
        visits["visit_date"]
    )

    as_of = orders["order_date"].max()

    # Remove ONLY the latest 30 days.
    cutoff = as_of - pd.Timedelta(days=30)

    remove_orders = orders[
        orders["outlet_id"].isin(scenario_ids)
        & (orders["order_date"] > cutoff)
        & (orders["order_date"] <= as_of)
    ]["order_id"]

    orders.drop(
        orders[
            orders["order_id"].isin(remove_orders)
        ].index,
        inplace=True,
    )

    # Remove corresponding order items.
    order_items.drop(
        order_items[
            order_items["order_id"].isin(remove_orders)
        ].index,
        inplace=True,
    )

    # Keep recent visits so the rep can still have attempted contact,
    # but make them non-productive.
    recent_visit_mask = (
        visits["outlet_id"].isin(scenario_ids)
        & (visits["visit_date"] > cutoff)
        & (visits["visit_date"] <= as_of)
    )

    visits.loc[
        recent_visit_mask,
        "productive_flag",
    ] = False

    print(
        f"Inactive scenarios modified: "
        f"{len(scenario_ids):,}"
    )

    return orders, order_items, visits


def modify_stock_risk(
    inventory,
    scenario_ids,
):
    """
    Create explicit repeated stockout behavior at outlet level.

    Selected outlets receive several stockout events and low
    closing inventory.
    """

    inventory["snapshot_date"] = pd.to_datetime(
        inventory["snapshot_date"]
    )

    mask = inventory["outlet_id"].isin(
        scenario_ids
    )

    scenario_inventory = inventory.loc[
        mask
    ].copy()

    if len(scenario_inventory) == 0:
        return inventory

    # Force a meaningful subset of snapshots into stockout state.
    selected_index = scenario_inventory.sample(
        frac=0.18,
        random_state=SEED,
    ).index

    inventory.loc[
        selected_index,
        "closing_stock",
    ] = 0

    inventory.loc[
        selected_index,
        "stockout_flag",
    ] = True

    # Remaining snapshots have low inventory.
    remaining_index = (
        scenario_inventory.index
        .difference(selected_index)
    )

    inventory.loc[
        remaining_index,
        "closing_stock",
    ] = np.minimum(
        inventory.loc[
            remaining_index,
            "closing_stock",
        ],
        3,
    )

    print(
        f"Stock-risk scenarios modified: "
        f"{len(scenario_ids):,}"
    )

    return inventory


def create_cross_sell_ground_truth(
    outlets,
    orders,
    order_items,
    products,
    scenario_ids,
):
    """
    Create deterministic cross-sell ground truth.

    For each selected outlet:
      - identify categories already purchased
      - identify top categories in its territory
      - select a territory-popular category not yet purchased
        by the outlet

    No synthetic sales are added.
    """

    # order_items does not contain outlet_id directly.
    # Recover outlet_id through orders.
    outlet_products = order_items.merge(
        orders[
            [
                "order_id",
                "outlet_id",
            ]
        ],
        on="order_id",
        how="left",
    )

    outlet_products = outlet_products.merge(
        outlets[
            [
                "outlet_id",
                "territory_id",
            ]
        ],
        on="outlet_id",
        how="left",
    )

    outlet_products = outlet_products.merge(
        products[
            [
                "product_id",
                "category",
            ]
        ],
        on="product_id",
        how="left",
    )

    category_counts = (
        outlet_products.groupby(
            [
                "outlet_id",
                "territory_id",
                "category",
            ]
        )["order_id"]
        .nunique()
        .reset_index(
            name="orders"
        )
    )

    # Category popularity by territory.
    territory_category = (
        category_counts.groupby(
            [
                "territory_id",
                "category",
            ]
        )["orders"]
        .sum()
        .reset_index()
    )

    territory_category[
        "territory_rank"
    ] = territory_category.groupby(
        "territory_id"
    )["orders"].rank(
        ascending=False,
        method="first",
    )

    top_categories = territory_category[
        territory_category["territory_rank"] <= 3
    ]

    records = []

    for outlet_id in scenario_ids:

        outlet_rows = category_counts[
            category_counts["outlet_id"]
            == outlet_id
        ]

        if outlet_rows.empty:
            continue

        territory_id = outlet_rows[
            "territory_id"
        ].iloc[0]

        purchased_categories = set(
            outlet_rows["category"]
        )

        territory_top = top_categories[
            top_categories["territory_id"]
            == territory_id
        ]

        candidates = territory_top[
            ~territory_top["category"].isin(
                purchased_categories
            )
        ]

        if candidates.empty:
            continue

        target_category = candidates.iloc[0][
            "category"
        ]

        records.append(
            {
                "outlet_id": outlet_id,
                "cross_sell_category": target_category,
                "cross_sell_scenario": 1,
            }
        )

    return pd.DataFrame(records)


def build_ground_truth(
    outlets,
    scenario_groups,
    cross_sell_truth,
):
    """
    Build explicit scenario labels for evaluation.
    """

    truth = outlets[
        ["outlet_id"]
    ].copy()

    truth[
        "revenue_decline_scenario"
    ] = truth["outlet_id"].isin(
        scenario_groups[
            "revenue_decline_scenario"
        ]
    ).astype(int)

    truth[
        "inactive_scenario"
    ] = truth["outlet_id"].isin(
        scenario_groups[
            "inactive_scenario"
        ]
    ).astype(int)

    truth[
        "stock_risk_scenario"
    ] = truth["outlet_id"].isin(
        scenario_groups[
            "stock_risk_scenario"
        ]
    ).astype(int)

    truth[
        "cross_sell_scenario"
    ] = truth["outlet_id"].isin(
        scenario_groups[
            "cross_sell_scenario"
        ]
    ).astype(int)

    truth = truth.merge(
        cross_sell_truth,
        on="outlet_id",
        how="left",
        suffixes=(
            "",
            "_detail",
        ),
    )

    truth[
        "cross_sell_category"
    ] = truth[
        "cross_sell_category"
    ].fillna("")

    return truth


def validate_counts(
    truth,
):
    print("\n" + "=" * 70)
    print("SCENARIO COUNTS")
    print("=" * 70)

    for column in [
        "revenue_decline_scenario",
        "inactive_scenario",
        "stock_risk_scenario",
        "cross_sell_scenario",
    ]:
        print(
            f"{column:<30}"
            f"{truth[column].sum():>8}"
        )


def main():

    print("=" * 70)
    print("SALESFORGE — SCENARIO GENERATOR V4")
    print("=" * 70)

    # ------------------------------------------------------------
    # Copy original baseline dataset
    # ------------------------------------------------------------

    copy_base_data()

    # ------------------------------------------------------------
    # Load V4 working copies
    # ------------------------------------------------------------

    outlets = pd.read_csv(
        OUTPUT / "outlets.csv"
    )

    orders = pd.read_csv(
        OUTPUT / "orders.csv"
    )

    order_items = pd.read_csv(
        OUTPUT / "order_items.csv"
    )

    visits = pd.read_csv(
        OUTPUT / "visits.csv"
    )

    inventory = pd.read_csv(
        OUTPUT / "inventory_snapshots.csv"
    )

    products = pd.read_csv(
        OUTPUT / "products.csv"
    )

    # ------------------------------------------------------------
    # Select controlled scenarios
    # ------------------------------------------------------------

    scenario_groups = choose_scenarios(
    outlets,
    orders,
    )

    print("\nScenario assignment:")

    for name, ids in scenario_groups.items():
        print(
            f"{name:<30}"
            f"{len(ids):>8}"
        )

    # ------------------------------------------------------------
    # Apply scenarios
    # ------------------------------------------------------------

    orders, order_items = modify_revenue_decline(
        orders,
        order_items,
        scenario_groups[
            "revenue_decline_scenario"
        ],
    )

    orders, order_items, visits = modify_inactive(
        orders,
        order_items,
        visits,
        scenario_groups[
            "inactive_scenario"
        ],
    )

    inventory = modify_stock_risk(
        inventory,
        scenario_groups[
            "stock_risk_scenario"
        ],
    )

    # ------------------------------------------------------------
    # Cross-sell ground truth
    # ------------------------------------------------------------

    cross_sell_truth = create_cross_sell_ground_truth(
        outlets,
        orders,
        order_items,
        products,
        scenario_groups[
            "cross_sell_scenario"
        ],
    )

    # ------------------------------------------------------------
    # Save modified datasets
    # ------------------------------------------------------------

    orders.to_csv(
        OUTPUT / "orders.csv",
        index=False,
    )

    order_items.to_csv(
        OUTPUT / "order_items.csv",
        index=False,
    )

    visits.to_csv(
        OUTPUT / "visits.csv",
        index=False,
    )

    inventory.to_csv(
        OUTPUT / "inventory_snapshots.csv",
        index=False,
    )

    # ------------------------------------------------------------
    # Ground truth
    # ------------------------------------------------------------

    truth = build_ground_truth(
        outlets,
        scenario_groups,
        cross_sell_truth,
    )

    truth.to_csv(
        OUTPUT / "scenario_ground_truth.csv",
        index=False,
    )

    validate_counts(truth)

    print("\nOutput directory:")
    print(OUTPUT)

    print("\nScenario generator V4 complete.")


if __name__ == "__main__":
    main()