from pathlib import Path
import json
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]


FEATURES = (
    ROOT
    / "data"
    / "processed_v4"
    / "outlet_features.csv"
)

OUTPUT_DIR = ROOT / "data" / "processed_v4"


OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# ============================================================
# REVENUE RECOVERY
# ============================================================

def revenue_recovery(row):

    growth = row["revenue_growth_30d"]
    gap = row["revenue_gap_vs_previous_30d"]
    previous_revenue = row["revenue_previous_30d"]
    current_orders = row["orders_30d"]
    order_growth = row["order_frequency_growth_30d"]
    peer_gap = row["revenue_growth_gap_vs_peer"]

    # Must have meaningful historical revenue.
    if previous_revenue < 1000:
        return None

    # Need a valid growth calculation.
    if pd.isna(growth):
        return None

    # --------------------------------------------------------
    # Prevent inactive outlets from being classified as
    # revenue-recovery opportunities.
    #
    # Revenue Recovery should represent a decline from an
    # actively ordering outlet, while INACTIVE_OUTLET handles
    # outlets with zero current-period orders.
    # --------------------------------------------------------

    if current_orders <= 0:
        return None

    # Core detection condition.
    if not (
        growth <= -0.30
        and gap >= 1000
    ):
        return None

    evidence = [
        (
            f"Revenue declined "
            f"{abs(growth) * 100:.1f}% vs previous 30d"
        ),
        (
            f"Revenue gap of ₹{gap:,.0f}"
        ),
    ]

    score = 50

    # --------------------------------------------------------
    # Business impact
    # --------------------------------------------------------

    if gap >= 10000:
        score += 25
    elif gap >= 5000:
        score += 20
    elif gap >= 2000:
        score += 10

    # --------------------------------------------------------
    # Severity of deterioration
    # --------------------------------------------------------

    if growth <= -0.60:
        score += 15
    elif growth <= -0.45:
        score += 10

    # --------------------------------------------------------
    # Corroborating order-frequency signal
    # --------------------------------------------------------

    if (
        pd.notna(order_growth)
        and order_growth <= -0.25
    ):
        score += 10

        evidence.append(
            (
                f"Order frequency declined "
                f"{abs(order_growth) * 100:.1f}%"
            )
        )

    # --------------------------------------------------------
    # Peer evidence
    # --------------------------------------------------------

    if (
        pd.notna(peer_gap)
        and peer_gap <= -0.25
    ):
        evidence.append(
            "Revenue growth materially below "
            "peer benchmark"
        )

    score = min(score, 100)

    if score >= 75:
        priority = "HIGH"
    elif score >= 55:
        priority = "MEDIUM"
    else:
        priority = "LOW"

    return {
        "opportunity_type": "REVENUE_RECOVERY",
        "score": score,
        "priority": priority,
        "evidence": evidence,
        "recommended_action": (
            "Prioritize an outlet visit to investigate "
            "lost volume and identify opportunities to "
            "recover recent revenue."
        ),
    }


# ============================================================
# INACTIVE OUTLET
# ============================================================

def inactive_outlet(row):

    days = row["days_since_last_order"]
    previous_revenue = row["revenue_previous_30d"]

    # Must have meaningful historical revenue.
    if previous_revenue < 1000:
        return None

    # V4 benchmark defines inactivity as 30+ days without
    # a current order.
    if days < 30:
        return None

    evidence = [
        f"No order for {days:.0f} days",
        (
            f"Previous 30d revenue was "
            f"₹{previous_revenue:,.0f}"
        ),
    ]

    # --------------------------------------------------------
    # Severity based on inactivity duration
    # --------------------------------------------------------

    if days >= 60:
        score = 95
        priority = "HIGH"

    elif days >= 45:
        score = 80
        priority = "HIGH"

    else:
        score = 65
        priority = "MEDIUM"

    # Zero current revenue is additional evidence.
    if row["revenue_30d"] == 0:

        score = min(
            score + 5,
            100,
        )

        evidence.append(
            "Zero revenue in current 30d"
        )

    return {
        "opportunity_type": "INACTIVE_OUTLET",
        "score": score,
        "priority": priority,
        "evidence": evidence,
        "recommended_action": (
            "Prioritize a reactivation visit and investigate "
            "why the outlet stopped ordering."
        ),
    }


# ============================================================
# STOCK RISK
# ============================================================

def stock_risk(row):

    events = row["stockout_events_90d"]
    rate = row["stockout_rate_90d"]
    closing_stock = row["avg_closing_stock_90d"]

    # Minimum repeated stockout evidence.
    if events < 2:
        return None

    evidence = [
        (
            f"{events:.0f} stockout events "
            f"in last 90d"
        ),
    ]

    score = 65

    # --------------------------------------------------------
    # Repeated stockout severity
    # --------------------------------------------------------

    if events >= 4:
        score += 20

    elif events >= 3:
        score += 10

    # --------------------------------------------------------
    # Stockout rate
    # --------------------------------------------------------

    if rate >= 0.05:

        score += 10

        evidence.append(
            f"Stockout rate: {rate * 100:.2f}%"
        )

    # --------------------------------------------------------
    # Low average closing inventory
    # --------------------------------------------------------

    if closing_stock <= 1:

        score += 5

        evidence.append(
            (
                f"Average closing stock: "
                f"{closing_stock:.1f} units"
            )
        )

    score = min(
        score,
        100,
    )

    priority = (
        "HIGH"
        if score >= 75
        else "MEDIUM"
    )

    return {
        "opportunity_type": "STOCK_RISK",
        "score": score,
        "priority": priority,
        "evidence": evidence,
        "recommended_action": (
            "Review affected inventory and prioritize "
            "replenishment before further stockouts "
            "cause lost sales."
        ),
    }


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print("SALESFORGE — OPPORTUNITY ENGINE V4")
    print("=" * 70)

    # --------------------------------------------------------
    # Load feature store
    # --------------------------------------------------------

    df = pd.read_csv(
        FEATURES
    )

    print(
        f"Feature rows loaded: "
        f"{len(df):,}"
    )

    opportunities = []

    # --------------------------------------------------------
    # Run opportunity detectors
    # --------------------------------------------------------

    for _, row in df.iterrows():

        detectors = [
            revenue_recovery(row),
            inactive_outlet(row),
            stock_risk(row),
        ]

        for opportunity in detectors:

            if opportunity is None:
                continue

            opportunity_id = (
                f"OPP-{len(opportunities) + 1:06d}"
            )

            opportunities.append(
                {
                    "opportunity_id": opportunity_id,
                    "outlet_id": row["outlet_id"],
                    "outlet_name": row["outlet_name"],
                    "territory_id": row["territory_id"],
                    "rep_id": row["rep_id"],
                    "outlet_type": row["outlet_type"],
                    "tier": row["tier"],
                    "opportunity_type": (
                        opportunity[
                            "opportunity_type"
                        ]
                    ),
                    "score": opportunity["score"],
                    "priority": opportunity["priority"],
                    "evidence": json.dumps(
                        opportunity["evidence"]
                    ),
                    "recommended_action": (
                        opportunity[
                            "recommended_action"
                        ]
                    ),
                    "status": "OPEN",
                }
            )

    result = pd.DataFrame(
        opportunities
    )

    # --------------------------------------------------------
    # Save V4 output
    # --------------------------------------------------------

    output = (
        OUTPUT_DIR
        / "opportunities_v4.csv"
    )

    result.to_csv(
        output,
        index=False,
    )

    # --------------------------------------------------------
    # Results
    # --------------------------------------------------------

    print("\n" + "=" * 70)
    print("RESULT")
    print("=" * 70)

    print(
        f"Opportunities detected: "
        f"{len(result):,}"
    )

    if not result.empty:

        print("\nBy type:")

        print(
            result[
                "opportunity_type"
            ]
            .value_counts()
            .to_string()
        )

        print("\nBy priority:")

        print(
            result[
                "priority"
            ]
            .value_counts()
            .to_string()
        )

        print("\nScore distribution:")

        print(
            result["score"]
            .describe()
            .to_string()
        )

        print("\nTop 15:")

        print(
            result[
                [
                    "opportunity_id",
                    "outlet_id",
                    "opportunity_type",
                    "score",
                    "priority",
                ]
            ]
            .sort_values(
                "score",
                ascending=False,
            )
            .head(15)
            .to_string(
                index=False
            )
        )

        # ----------------------------------------------------
        # Example top opportunity
        # ----------------------------------------------------

        top = (
            result
            .sort_values(
                "score",
                ascending=False,
            )
            .iloc[0]
        )

        print("\nExample:")

        print(
            f"Outlet: "
            f"{top['outlet_name']}"
        )

        print(
            f"Type: "
            f"{top['opportunity_type']}"
        )

        print(
            f"Score: "
            f"{top['score']}"
        )

        print(
            f"Priority: "
            f"{top['priority']}"
        )

        print(
            "Evidence:",
            json.loads(
                top["evidence"]
            ),
        )

    print(
        f"\nSaved to: "
        f"{output}"
    )

    print(
        "\nOpportunity Engine V4 complete."
    )


if __name__ == "__main__":
    main()