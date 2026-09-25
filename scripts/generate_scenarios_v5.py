from pathlib import Path
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

INPUT = ROOT / "data" / "generated"
OUTPUT = ROOT / "data" / "generated_v5"

SEED = 42
rng = np.random.default_rng(SEED)

OUTPUT.mkdir(
    parents=True,
    exist_ok=True,
)


def copy_base_data():
    """
    Copy the original generated dataset into generated_v5.

    All scenarios are applied to this clean baseline.
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

        df.to_csv(
            destination,
            index=False,
        )

        print(
            f"Copied {filename:<28}"
            f"{len(df):>10,} rows"
        )


def choose_scenarios(
    outlets,
    orders,
    inventory,
    order_items,
    products,
):
    """
    Select controlled, non-overlapping scenario groups.

    Revenue decline:
        - Previous 30d revenue >= 1,000
        - Previous 30d orders > 0
        - Current 30d orders >= 2
        - Current 30d revenue >= 1,000
        - Baseline current revenue <= previous revenue
        - After the 45% revenue multiplier, the expected
          revenue gap is >= 1,000

    Inactive:
        - Previous 30d revenue >= 1,000
        - Previous 30d orders > 0

    Stock risk:
        - At least 4 inventory snapshots inside the latest
          90-day feature window

    Cross-sell:
        - Remaining outlets
        - Must have at least one un-purchased product category
    """

    outlet_ids = outlets[
        "outlet_id"
    ].tolist()

    rng.shuffle(outlet_ids)

    orders = orders.copy()
    inventory = inventory.copy()

    orders["order_date"] = pd.to_datetime(
        orders["order_date"]
    )

    inventory["snapshot_date"] = pd.to_datetime(
        inventory["snapshot_date"]
    )

    # ============================================================
    # DATE WINDOWS
    # ============================================================

    as_of = orders[
        "order_date"
    ].max()

    current_start = (
        as_of
        - pd.Timedelta(days=30)
    )

    previous_start = (
        as_of
        - pd.Timedelta(days=60)
    )

    inventory_start = (
        as_of
        - pd.Timedelta(days=90)
    )

    # ============================================================
    # CURRENT 30-DAY ACTIVITY
    # ============================================================

    current_orders = orders[
        (orders["order_date"] > current_start)
        & (orders["order_date"] <= as_of)
    ]

    current_activity = (
        current_orders
        .groupby("outlet_id")
        .agg(
            current_revenue=(
                "net_value",
                "sum",
            ),
            current_orders=(
                "order_id",
                "nunique",
            ),
        )
    )

    # ============================================================
    # PREVIOUS 30-DAY ACTIVITY
    # ============================================================

    previous_orders = orders[
        (orders["order_date"] > previous_start)
        & (orders["order_date"] <= current_start)
    ]

    previous_activity = (
        previous_orders
        .groupby("outlet_id")
        .agg(
            previous_revenue=(
                "net_value",
                "sum",
            ),
            previous_orders=(
                "order_id",
                "nunique",
            ),
        )
    )

    activity = (
        pd.DataFrame(
            {
                "outlet_id": outlet_ids
            }
        )
        .merge(
            current_activity,
            on="outlet_id",
            how="left",
        )
        .merge(
            previous_activity,
            on="outlet_id",
            how="left",
        )
        .fillna(0)
    )

    # ============================================================
    # REVENUE DECLINE
    # ============================================================

    # After applying 0.45 multiplier:
    #
    # expected revenue gap =
    # previous_revenue - (current_revenue * 0.45)
    #
    # Require that gap itself to be >= 1,000.
    revenue_candidates_df = activity[
        (activity["previous_revenue"] >= 1000)
        & (activity["previous_orders"] > 0)
        & (activity["current_orders"] >= 2)
        & (activity["current_revenue"] >= 1000)
        & (
            activity["current_revenue"]
            <= activity["previous_revenue"]
        )
        & (
            activity["previous_revenue"]
            - (
                activity["current_revenue"]
                * 0.45
            )
            >= 1000
        )
    ]

    revenue_candidate_ids = set(
        revenue_candidates_df[
            "outlet_id"
        ]
    )

    revenue_candidates = [
        outlet_id
        for outlet_id in outlet_ids
        if outlet_id in revenue_candidate_ids
    ]

    if len(revenue_candidates) < 120:
        raise ValueError(
            "Not enough eligible outlets for "
            "revenue-decline scenario. "
            f"Required: 120, "
            f"Available: {len(revenue_candidates)}"
        )

    decline_ids = revenue_candidates[
        :120
    ]

    decline_set = set(
        decline_ids
    )

    # ============================================================
    # INACTIVE
    # ============================================================

    inactive_candidates_df = activity[
        (activity["previous_revenue"] >= 1000)
        & (activity["previous_orders"] > 0)
        & (
            ~activity["outlet_id"].isin(
                decline_set
            )
        )
    ]

    inactive_candidate_ids = set(
        inactive_candidates_df[
            "outlet_id"
        ]
    )

    inactive_candidates = [
        outlet_id
        for outlet_id in outlet_ids
        if outlet_id in inactive_candidate_ids
    ]

    if len(inactive_candidates) < 100:
        raise ValueError(
            "Not enough eligible outlets for "
            "inactive scenario. "
            f"Required: 100, "
            f"Available: {len(inactive_candidates)}"
        )

    inactive_ids = inactive_candidates[
        :100
    ]

    inactive_set = set(
        inactive_ids
    )

    # ============================================================
    # STOCK-RISK
    #
    # IMPORTANT:
    # Eligibility is based on the SAME 90-day window
    # used by the feature store.
    # ============================================================

    inventory_90 = inventory[
        (inventory["snapshot_date"] > inventory_start)
        & (inventory["snapshot_date"] <= as_of)
    ]

    inventory_counts = (
        inventory_90
        .groupby("outlet_id")
        .size()
    )

    eligible_inventory_outlets = set(
        inventory_counts[
            inventory_counts >= 4
        ].index
    )

    remaining_ids = [
        outlet_id
        for outlet_id in outlet_ids
        if (
            outlet_id not in decline_set
            and outlet_id not in inactive_set
            and outlet_id in eligible_inventory_outlets
        )
    ]

    if len(remaining_ids) < 110:
        raise ValueError(
            "Not enough outlets with >=4 inventory "
            "snapshots in the latest 90 days. "
            f"Required: 110, "
            f"Available: {len(remaining_ids)}"
        )

    stock_ids = remaining_ids[
        :110
    ]

    stock_set = set(
        stock_ids
    )

    # ============================================================
    # CROSS-SELL
    #
    # Cross-sell is defined against the outlet's CURRENT assortment,
    # using the same latest-90-day window as the feature store.
    # We intentionally do NOT use all-time category history here:
    # an outlet may have bought a category years ago but still have
    # a meaningful current distribution gap.
    # ============================================================

    remaining_ids = [
        outlet_id
        for outlet_id in outlet_ids
        if (
            outlet_id not in decline_set
            and outlet_id not in inactive_set
            and outlet_id not in stock_set
        )
    ]

    orders_x = orders.copy()
    order_items_x = order_items.copy()
    products_x = products.copy()

    orders_x["order_date"] = pd.to_datetime(
        orders_x["order_date"]
    )
    orders_x["order_id"] = orders_x[
        "order_id"
    ].astype(str)
    orders_x["outlet_id"] = orders_x[
        "outlet_id"
    ].astype(str)

    order_items_x["order_id"] = order_items_x[
        "order_id"
    ].astype(str)
    order_items_x["product_id"] = order_items_x[
        "product_id"
    ].astype(str)

    products_x["product_id"] = products_x[
        "product_id"
    ].astype(str)
    products_x["category"] = products_x[
        "category"
    ].astype(str)

    as_of = orders_x["order_date"].max()
    assortment_start = (
        as_of - pd.Timedelta(days=90)
    )

    recent_orders = orders_x[
        (orders_x["order_date"] > assortment_start)
        & (orders_x["order_date"] <= as_of)
    ][
        [
            "order_id",
            "outlet_id",
        ]
    ].copy()

    recent_transactions = (
        order_items_x[
            [
                "order_id",
                "product_id",
            ]
        ]
        .merge(
            recent_orders,
            on="order_id",
            how="inner",
        )
        .merge(
            products_x[
                [
                    "product_id",
                    "category",
                ]
            ],
            on="product_id",
            how="inner",
        )
    )

    all_categories = set(
        products_x["category"]
        .dropna()
        .astype(str)
        .unique()
    )

    if not all_categories:
        raise ValueError(
            "No product categories available for cross-sell "
            "scenario selection."
        )

    # Number of distinct categories currently purchased by each outlet.
    # The 90-day window matches outlet_features.csv.
    purchased_category_count = (
        recent_transactions
        .groupby("outlet_id")["category"]
        .nunique()
    )

    eligible_cross_sell_ids = [
        outlet_id
        for outlet_id in remaining_ids
        if (
            purchased_category_count.get(
                str(outlet_id),
                0,
            )
            < len(all_categories)
        )
    ]

    print(
        "Cross-sell eligibility window: "
        f"{assortment_start.date()} to {as_of.date()}"
    )

    print(
        "Cross-sell eligible outlets: "
        f"{len(eligible_cross_sell_ids):,}"
    )

    if len(eligible_cross_sell_ids) < 140:
        raise ValueError(
            "Not enough eligible outlets for cross-sell scenario. "
            f"Required: 140, "
            f"Available: {len(eligible_cross_sell_ids)}. "
            "Eligibility is based on categories purchased in the "
            "latest 90 days, matching the feature-store assortment "
            "window."
        )

    cross_sell_ids = eligible_cross_sell_ids[
        :140
    ]

    return {
        "revenue_decline_scenario": set(
            decline_ids
        ),
        "inactive_scenario": set(
            inactive_ids
        ),
        "stock_risk_scenario": set(
            stock_ids
        ),
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
    Create a controlled revenue-decline scenario.

    All current-period orders receive a 45% revenue multiplier.

    Approximately 35% of current orders are removed, but at least
    one current-period order is always retained for every planted
    revenue-decline outlet.
    """

    orders["order_date"] = pd.to_datetime(
        orders["order_date"]
    )

    as_of = orders[
        "order_date"
    ].max()

    current_start = (
        as_of
        - pd.Timedelta(days=30)
    )

    current_mask = (
        orders["outlet_id"].isin(
            scenario_ids
        )
        & (orders["order_date"] > current_start)
        & (orders["order_date"] <= as_of)
    )

    current_orders = orders.loc[
        current_mask
    ].copy()

    # ------------------------------------------------------------
    # Apply revenue reduction to ALL recent orders.
    # ------------------------------------------------------------

    orders.loc[
        current_mask,
        "gross_value",
    ] *= 0.45

    orders.loc[
        current_mask,
        "discount_value",
    ] *= 0.45

    orders.loc[
        current_mask,
        "net_value",
    ] *= 0.45

    # ------------------------------------------------------------
    # Remove approximately 35% of orders.
    #
    # IMPORTANT:
    # Never remove the final current-period order for
    # a planted revenue-decline outlet.
    # ------------------------------------------------------------

    remove_ids = []

    for outlet_id in scenario_ids:

        outlet_orders = current_orders[
            current_orders["outlet_id"] == outlet_id
        ]

        n_orders = len(
            outlet_orders
        )

        if n_orders <= 1:
            continue

        n_remove = int(
            np.floor(
                n_orders * 0.35
            )
        )

        # Never remove every order.
        n_remove = min(
            n_remove,
            n_orders - 1,
        )

        if n_remove <= 0:
            continue

        selected = outlet_orders.sample(
            n=n_remove,
            random_state=SEED + int(outlet_id),
        )

        remove_ids.extend(
            selected["order_id"].tolist()
        )

    if remove_ids:

        remove_ids = set(
            remove_ids
        )

        orders.drop(
            orders[
                orders["order_id"].isin(
                    remove_ids
                )
            ].index,
            inplace=True,
        )

        order_items.drop(
            order_items[
                order_items["order_id"].isin(
                    remove_ids
                )
            ].index,
            inplace=True,
        )

    print(
        f"Revenue decline scenarios modified: "
        f"{len(scenario_ids):,}"
    )

    print(
        f"Recent orders removed: "
        f"{len(remove_ids):,}"
    )

    return (
        orders,
        order_items,
    )


def modify_inactive(
    orders,
    order_items,
    visits,
    scenario_ids,
):
    """
    Remove only the latest 30 days of orders.

    This preserves the previous 30-day period so the outlet
    has a measurable historical baseline.
    """

    orders["order_date"] = pd.to_datetime(
        orders["order_date"]
    )

    visits["visit_date"] = pd.to_datetime(
        visits["visit_date"]
    )

    as_of = orders[
        "order_date"
    ].max()

    cutoff = (
        as_of
        - pd.Timedelta(days=30)
    )

    remove_orders = orders[
        orders["outlet_id"].isin(
            scenario_ids
        )
        & (orders["order_date"] > cutoff)
        & (orders["order_date"] <= as_of)
    ]["order_id"]

    orders.drop(
        orders[
            orders["order_id"].isin(
                remove_orders
            )
        ].index,
        inplace=True,
    )

    order_items.drop(
        order_items[
            order_items["order_id"].isin(
                remove_orders
            )
        ].index,
        inplace=True,
    )

    # Keep recent visits but make them non-productive.
    recent_visit_mask = (
        visits["outlet_id"].isin(
            scenario_ids
        )
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

    return (
        orders,
        order_items,
        visits,
    )


def modify_stock_risk(
    inventory,
    scenario_ids,
):
    """
    Create controlled stock-risk scenarios inside the exact
    90-day window consumed by the feature store.

    For every selected outlet:

    - At least 5% of 90-day inventory snapshots become
      explicit stockout events.
    - At least 4 stockout events are guaranteed.
    - All remaining 90-day closing stock is capped at 1.

    This directly aligns the scenario generator with the
    feature-store definitions.
    """

    inventory["snapshot_date"] = pd.to_datetime(
        inventory["snapshot_date"]
    )

    as_of = inventory[
        "snapshot_date"
    ].max()

    inventory_start = (
        as_of
        - pd.Timedelta(days=90)
    )

    recent_mask = (
        inventory["snapshot_date"] > inventory_start
    ) & (
        inventory["snapshot_date"] <= as_of
    )

    scenario_mask = inventory[
        "outlet_id"
    ].isin(
        scenario_ids
    )

    recent_scenario_mask = (
        recent_mask
        & scenario_mask
    )

    recent_scenario_inventory = inventory.loc[
        recent_scenario_mask
    ].copy()

    if recent_scenario_inventory.empty:
        raise ValueError(
            "No recent inventory rows found for "
            "stock-risk scenario outlets."
        )

    stockout_indices = []

    # ------------------------------------------------------------
    # Process each selected outlet independently.
    # ------------------------------------------------------------

    for outlet_id in scenario_ids:

        outlet_inventory = (
            recent_scenario_inventory[
                recent_scenario_inventory[
                    "outlet_id"
                ] == outlet_id
            ]
        )

        n_snapshots = len(
            outlet_inventory
        )

        if n_snapshots < 4:
            raise ValueError(
                f"Outlet {outlet_id} has only "
                f"{n_snapshots} inventory snapshots "
                "inside the 90-day feature window."
            )

        # At least 5%, but never fewer than 4.
        n_stockouts = max(
            4,
            int(
                np.ceil(
                    n_snapshots * 0.05
                )
            ),
        )

        n_stockouts = min(
            n_stockouts,
            n_snapshots,
        )

        selected = outlet_inventory.sample(
            n=n_stockouts,
            random_state=SEED + int(outlet_id),
        ).index

        stockout_indices.extend(
            selected.tolist()
        )

    stockout_indices = pd.Index(
        stockout_indices
    )

    # ------------------------------------------------------------
    # Make ALL remaining 90-day inventory low stock.
    # ------------------------------------------------------------

    recent_indices = recent_scenario_inventory.index

    inventory.loc[
        recent_indices,
        "closing_stock",
    ] = np.minimum(
        inventory.loc[
            recent_indices,
            "closing_stock",
        ],
        1,
    )

    # ------------------------------------------------------------
    # Explicit stockout snapshots.
    # ------------------------------------------------------------

    inventory.loc[
        stockout_indices,
        "closing_stock",
    ] = 0

    inventory.loc[
        stockout_indices,
        "stockout_flag",
    ] = True

    # ------------------------------------------------------------
    # Diagnostics.
    # ------------------------------------------------------------

    recent_after = inventory.loc[
        recent_scenario_mask
    ]

    event_counts = (
        recent_after
        .groupby("outlet_id")[
            "stockout_flag"
        ]
        .sum()
    )

    snapshot_counts = (
        recent_after
        .groupby("outlet_id")
        .size()
    )

    stockout_rates = (
        event_counts
        / snapshot_counts
    )

    avg_stock = (
        recent_after
        .groupby("outlet_id")[
            "closing_stock"
        ]
        .mean()
    )

    print(
        f"Stock-risk scenarios modified: "
        f"{len(scenario_ids):,}"
    )

    print(
        f"Explicit stockout snapshots created: "
        f"{len(stockout_indices):,}"
    )

    print(
        "\nStockout events per selected outlet:"
    )

    print(
        event_counts.describe()
    )

    print(
        "\nStockout rate per selected outlet:"
    )

    print(
        stockout_rates.describe()
    )

    print(
        "\nAverage closing stock per selected outlet:"
    )

    print(
        avg_stock.describe()
    )

    print(
        f"\nOutlets with >=3 stockout events: "
        f"{(event_counts >= 3).sum()}/"
        f"{len(scenario_ids)}"
    )

    print(
        f"Outlets with stockout rate >=5%: "
        f"{(stockout_rates >= 0.05).sum()}/"
        f"{len(scenario_ids)}"
    )

    print(
        f"Outlets with avg closing stock <=1: "
        f"{(avg_stock <= 1).sum()}/"
        f"{len(scenario_ids)}"
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

    Cross-sell is based on the outlet's latest 90-day assortment,
    matching the feature-store definition. Each planted outlet gets
    exactly one category that is not currently purchased.
    """

    scenario_ids = [str(x) for x in list(scenario_ids)]

    outlets_x = outlets.copy()
    orders_x = orders.copy()
    order_items_x = order_items.copy()
    products_x = products.copy()

    outlets_x["outlet_id"] = (
        outlets_x["outlet_id"].astype(str)
    )
    outlets_x["territory_id"] = (
        outlets_x["territory_id"].astype(str)
    )

    orders_x["outlet_id"] = (
        orders_x["outlet_id"].astype(str)
    )
    orders_x["order_id"] = (
        orders_x["order_id"].astype(str)
    )
    orders_x["order_date"] = pd.to_datetime(
        orders_x["order_date"]
    )

    order_items_x["order_id"] = (
        order_items_x["order_id"].astype(str)
    )
    order_items_x["product_id"] = (
        order_items_x["product_id"].astype(str)
    )

    products_x["product_id"] = (
        products_x["product_id"].astype(str)
    )
    products_x["category"] = (
        products_x["category"].astype(str)
    )

    all_categories = (
        products_x["category"]
        .dropna()
        .drop_duplicates()
        .tolist()
    )

    as_of = orders_x["order_date"].max()
    assortment_start = (
        as_of - pd.Timedelta(days=90)
    )

    recent_orders = orders_x[
        (orders_x["order_date"] > assortment_start)
        & (orders_x["order_date"] <= as_of)
    ][
        [
            "order_id",
            "outlet_id",
        ]
    ].copy()

    outlet_products = (
        order_items_x[
            [
                "order_id",
                "product_id",
            ]
        ]
        .merge(
            recent_orders,
            on="order_id",
            how="inner",
        )
        .merge(
            outlets_x[
                [
                    "outlet_id",
                    "territory_id",
                ]
            ],
            on="outlet_id",
            how="inner",
        )
        .merge(
            products_x[
                [
                    "product_id",
                    "category",
                ]
            ],
            on="product_id",
            how="inner",
        )
    )

    # Territory category popularity in the same recent window.
    territory_category = (
        outlet_products
        .groupby(
            [
                "territory_id",
                "category",
            ]
        )["order_id"]
        .nunique()
        .reset_index(name="orders")
    )

    territory_category["territory_rank"] = (
        territory_category
        .groupby("territory_id")["orders"]
        .rank(
            ascending=False,
            method="first",
        )
    )

    top_categories = territory_category[
        territory_category["territory_rank"] <= 5
    ].copy()

    purchased = (
        outlet_products[
            outlet_products["outlet_id"].isin(
                scenario_ids
            )
        ]
        .groupby("outlet_id")["category"]
        .apply(lambda x: set(x.astype(str)))
        .to_dict()
    )

    outlet_territories = (
        outlets_x[
            outlets_x["outlet_id"].isin(
                scenario_ids
            )
        ][
            [
                "outlet_id",
                "territory_id",
            ]
        ]
        .set_index("outlet_id")["territory_id"]
        .to_dict()
    )

    records = []

    for outlet_id in scenario_ids:
        territory_id = outlet_territories.get(
            outlet_id
        )

        if territory_id is None:
            raise ValueError(
                f"Cross-sell generation failed: outlet "
                f"{outlet_id} has no territory_id."
            )

        already_purchased = purchased.get(
            outlet_id,
            set(),
        )

        candidates = top_categories[
            top_categories["territory_id"]
            == territory_id
        ].copy()

        candidates = candidates[
            ~candidates["category"].astype(str).isin(
                already_purchased
            )
        ].sort_values(
            [
                "territory_rank",
                "orders",
            ],
            ascending=[
                True,
                False,
            ],
        )

        if not candidates.empty:
            target_category = str(
                candidates.iloc[0]["category"]
            )
        else:
            fallback_categories = [
                category
                for category in all_categories
                if category not in already_purchased
            ]

            if not fallback_categories:
                raise ValueError(
                    f"Cross-sell generation failed: outlet "
                    f"{outlet_id} has purchased every "
                    f"catalog category in the latest 90 days."
                )

            target_category = str(
                fallback_categories[0]
            )

        records.append(
            {
                "outlet_id": outlet_id,
                "cross_sell_category": target_category,
                "cross_sell_scenario": 1,
            }
        )

    result = pd.DataFrame(
        records,
        columns=[
            "outlet_id",
            "cross_sell_category",
            "cross_sell_scenario",
        ],
    )

    if len(result) != len(scenario_ids):
        raise ValueError(
            "Cross-sell ground truth is incomplete: "
            f"expected {len(scenario_ids)}, "
            f"generated {len(result)}."
        )

    if result["outlet_id"].nunique() != len(
        scenario_ids
    ):
        raise ValueError(
            "Cross-sell ground truth contains duplicate "
            "or missing outlet IDs."
        )

    return result


def build_ground_truth(
    outlets,
    scenario_groups,
    cross_sell_truth,
):
    """
    Build explicit scenario labels.

    Normalize outlet_id to one dtype before the final merge.
    CSV reloads and intermediate joins can otherwise produce
    int64 on the outlet table and string/object on cross_sell_truth.
    """

    truth = outlets[
        ["outlet_id"]
    ].copy()

    # Normalize outlet IDs once at the ground-truth boundary.
    # Scenario IDs may originate as numpy/pandas integers while
    # cross-sell truth is intentionally normalized to strings.
    truth["outlet_id"] = truth[
        "outlet_id"
    ].astype(str)

    normalized_groups = {
        name: {str(x) for x in ids}
        for name, ids in scenario_groups.items()
    }

    # ------------------------------------------------------------
    # Normalize merge key.
    # ------------------------------------------------------------

    truth["outlet_id"] = truth["outlet_id"].astype(str)

    cross_sell_truth = cross_sell_truth.copy()
    cross_sell_truth["outlet_id"] = (
        cross_sell_truth["outlet_id"].astype(str)
    )

    # Normalize scenario ID lists too, so .isin() uses the same
    # representation as truth["outlet_id"].
    scenario_groups = {
        name: [str(x) for x in ids]
        for name, ids in scenario_groups.items()
    }

    truth[
        "revenue_decline_scenario"
    ] = truth[
        "outlet_id"
    ].isin(
        normalized_groups["revenue_decline_scenario"]
    ).astype(int)

    truth[
        "inactive_scenario"
    ] = truth[
        "outlet_id"
    ].isin(
        normalized_groups["inactive_scenario"]
    ).astype(int)

    truth[
        "stock_risk_scenario"
    ] = truth[
        "outlet_id"
    ].isin(
        normalized_groups["stock_risk_scenario"]
    ).astype(int)

    truth[
        "cross_sell_scenario"
    ] = truth[
        "outlet_id"
    ].isin(
        normalized_groups["cross_sell_scenario"]
    ).astype(int)

    cross_sell_truth = cross_sell_truth.copy()
    cross_sell_truth["outlet_id"] = (
        cross_sell_truth["outlet_id"].astype(str)
    )

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
    print(
        "\n" + "=" * 70
    )

    print(
        "SCENARIO COUNTS"
    )

    print(
        "=" * 70
    )

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
    print(
        "SALESFORGE — SCENARIO GENERATOR V5"
    )
    print("=" * 70)

    # ------------------------------------------------------------
    # Copy clean baseline
    # ------------------------------------------------------------

    copy_base_data()

    # ------------------------------------------------------------
    # Load
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
    # Select scenarios
    # ------------------------------------------------------------

    scenario_groups = choose_scenarios(
        outlets,
        orders,
        inventory,
        order_items,
        products,
    )

    print(
        "\nScenario assignment:"
    )

    for name, ids in scenario_groups.items():

        print(
            f"{name:<30}"
            f"{len(ids):>8}"
        )

    # ------------------------------------------------------------
    # Apply revenue decline
    # ------------------------------------------------------------

    orders, order_items = (
        modify_revenue_decline(
            orders,
            order_items,
            scenario_groups[
                "revenue_decline_scenario"
            ],
        )
    )

    # ------------------------------------------------------------
    # Apply inactivity
    # ------------------------------------------------------------

    orders, order_items, visits = (
        modify_inactive(
            orders,
            order_items,
            visits,
            scenario_groups[
                "inactive_scenario"
            ],
        )
    )

    # ------------------------------------------------------------
    # Apply stock risk
    # ------------------------------------------------------------

    inventory = modify_stock_risk(
        inventory,
        scenario_groups[
            "stock_risk_scenario"
        ],
    )

    # ------------------------------------------------------------
    # Cross-sell ground truth
    # ------------------------------------------------------------

    cross_sell_truth = (
        create_cross_sell_ground_truth(
            outlets,
            orders,
            order_items,
            products,
            scenario_groups[
                "cross_sell_scenario"
            ],
        )
    )

    print(
        f"Cross-sell targets generated: "
        f"{len(cross_sell_truth)}/"
        f"{len(scenario_groups['cross_sell_scenario'])}"
    )

    # ------------------------------------------------------------
    # Save modified data
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

    validate_counts(
        truth
    )

    print(
        "\nOutput directory:"
    )

    print(
        OUTPUT
    )

    print(
        "\nScenario generator V5 complete."
    )


if __name__ == "__main__":
    main()