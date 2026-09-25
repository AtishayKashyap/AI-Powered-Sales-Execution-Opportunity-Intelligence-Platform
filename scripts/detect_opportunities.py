from pathlib import Path
import json
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
FEATURES = ROOT / "data" / "processed" / "outlet_features.csv"
OUTPUT_DIR = ROOT / "data" / "processed"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# Configuration
# ============================================================

MIN_REVENUE_GAP = 500
HIGH_REVENUE_GAP = 5000

MIN_INACTIVE_DAYS = 30
HIGH_INACTIVE_DAYS = 60

MIN_STOCKOUT_EVENTS = 1
HIGH_STOCKOUT_EVENTS = 3


def pct(value):
    if pd.isna(value):
        return None
    return float(value) * 100


def revenue_recovery(row):
    """
    Detect revenue deterioration, then calculate priority
    using both relative deterioration and absolute business impact.
    """

    growth = row["revenue_growth_30d"]
    gap = row["revenue_gap_vs_previous_30d"]
    previous_revenue = row["revenue_previous_30d"]
    orders_growth = row["order_frequency_growth_30d"]
    peer_gap = row["revenue_growth_gap_vs_peer"]

    # Cannot establish deterioration without a prior baseline.
    if previous_revenue <= 0 or pd.isna(growth):
        return None

    # We only care about actual revenue loss.
    if gap < MIN_REVENUE_GAP and growth > -0.15:
        return None

    evidence = []
    components = []

    # --------------------------------------------------------
    # Revenue deterioration
    # --------------------------------------------------------

    if growth <= -0.50:
        revenue_component = 35
        evidence.append(
            f"Revenue declined {abs(pct(growth)):.1f}% "
            f"vs previous 30d"
        )
    elif growth <= -0.30:
        revenue_component = 28
        evidence.append(
            f"Revenue declined {abs(pct(growth)):.1f}% "
            f"vs previous 30d"
        )
    elif growth <= -0.15:
        revenue_component = 20
        evidence.append(
            f"Revenue declined {abs(pct(growth)):.1f}% "
            f"vs previous 30d"
        )
    else:
        revenue_component = 0

    components.append(revenue_component)

    # --------------------------------------------------------
    # Absolute business impact
    # --------------------------------------------------------

    if gap >= HIGH_REVENUE_GAP:
        impact_component = 35
        evidence.append(
            f"Revenue gap of ₹{gap:,.0f}"
        )
    elif gap >= 2000:
        impact_component = 27
        evidence.append(
            f"Revenue gap of ₹{gap:,.0f}"
        )
    elif gap >= MIN_REVENUE_GAP:
        impact_component = 15
        evidence.append(
            f"Revenue gap of ₹{gap:,.0f}"
        )
    else:
        impact_component = 0

    components.append(impact_component)

    # --------------------------------------------------------
    # Order-frequency corroboration
    # --------------------------------------------------------

    if pd.notna(orders_growth):

        if orders_growth <= -0.50:
            order_component = 15
            evidence.append(
                f"Order frequency declined "
                f"{abs(pct(orders_growth)):.1f}%"
            )
        elif orders_growth <= -0.25:
            order_component = 10
            evidence.append(
                f"Order frequency declined "
                f"{abs(pct(orders_growth)):.1f}%"
            )
        elif orders_growth < 0:
            order_component = 5
            evidence.append(
                "Order frequency declined"
            )
        else:
            order_component = 0

        components.append(order_component)

    # --------------------------------------------------------
    # Peer corroboration
    # --------------------------------------------------------

    if pd.notna(peer_gap) and peer_gap <= -0.25:
        peer_component = 15
        evidence.append(
            "Revenue growth materially below peer benchmark"
        )
    elif pd.notna(peer_gap) and peer_gap < 0:
        peer_component = 5
        evidence.append(
            "Revenue growth below peer benchmark"
        )
    else:
        peer_component = 0

    components.append(peer_component)

    score = min(sum(components), 100)

    # Require enough evidence.
    if score < 35:
        return None

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
            "Prioritize an outlet visit to investigate lost "
            "volume, identify affected products/categories, "
            "and attempt revenue recovery."
        ),
    }


def inactive_outlet(row):
    """
    Detect previously active outlets that have stopped ordering.
    """

    days = row["days_since_last_order"]
    previous_revenue = row["revenue_previous_30d"]
    current_revenue = row["revenue_30d"]

    if previous_revenue <= 0:
        return None

    if days <= MIN_INACTIVE_DAYS:
        return None

    evidence = []

    # --------------------------------------------------------
    # Recency severity
    # --------------------------------------------------------

    if days >= HIGH_INACTIVE_DAYS:
        score = 60
        priority = "HIGH"

        evidence.append(
            f"No order for {days:.0f} days"
        )

    elif days >= 45:
        score = 45
        priority = "MEDIUM"

        evidence.append(
            f"No order for {days:.0f} days"
        )

    else:
        score = 30
        priority = "LOW"

        evidence.append(
            f"No order for {days:.0f} days"
        )

    # --------------------------------------------------------
    # Current inactivity
    # --------------------------------------------------------

    if current_revenue == 0:
        score += 20
        evidence.append(
            "Zero revenue in current 30d"
        )

    # --------------------------------------------------------
    # Historical value
    # --------------------------------------------------------

    if previous_revenue >= HIGH_REVENUE_GAP:
        score += 20
        evidence.append(
            f"Previous 30d revenue was "
            f"₹{previous_revenue:,.0f}"
        )
    elif previous_revenue >= 1000:
        score += 10
        evidence.append(
            f"Previous 30d revenue was "
            f"₹{previous_revenue:,.0f}"
        )

    score = min(score, 100)

    if score >= 75:
        priority = "HIGH"
    elif score >= 55:
        priority = "MEDIUM"
    else:
        priority = "LOW"

    return {
        "opportunity_type": "INACTIVE_OUTLET",
        "score": score,
        "priority": priority,
        "evidence": evidence,
        "recommended_action": (
            "Prioritize a reactivation visit. Investigate "
            "the reason for inactivity and attempt to recover "
            "previous purchasing behaviour."
        ),
    }


def stock_risk(row):
    """
    Detect repeated stockout events and inventory pressure.
    """

    events = row["stockout_events_90d"]
    rate = row["stockout_rate_90d"]
    closing_stock = row["avg_closing_stock_90d"]

    if events < MIN_STOCKOUT_EVENTS and rate < 0.05:
        return None

    evidence = []
    score = 0

    # --------------------------------------------------------
    # Stockout frequency
    # --------------------------------------------------------

    if events >= HIGH_STOCKOUT_EVENTS:
        score += 50
        evidence.append(
            f"{events:.0f} stockout events in last 90d"
        )
    elif events >= 2:
        score += 35
        evidence.append(
            f"{events:.0f} stockout events in last 90d"
        )
    else:
        score += 20
        evidence.append(
            f"{events:.0f} stockout event(s) in last 90d"
        )

    # --------------------------------------------------------
    # Stockout rate
    # --------------------------------------------------------

    if rate >= 0.10:
        score += 30
        evidence.append(
            f"Stockout rate: {rate * 100:.1f}%"
        )
    elif rate >= 0.05:
        score += 20
        evidence.append(
            f"Stockout rate: {rate * 100:.1f}%"
        )

    # --------------------------------------------------------
    # Closing inventory
    # --------------------------------------------------------

    if closing_stock <= 5:
        score += 20
        evidence.append(
            f"Average closing stock: "
            f"{closing_stock:.1f} units"
        )

    score = min(score, 100)

    if score >= 75:
        priority = "HIGH"
    elif score >= 55:
        priority = "MEDIUM"
    else:
        priority = "LOW"

    return {
        "opportunity_type": "STOCK_RISK",
        "score": score,
        "priority": priority,
        "evidence": evidence,
        "recommended_action": (
            "Review outlet inventory and prioritize "
            "replenishment of affected SKUs before another "
            "stockout causes lost sales."
        ),
    }


def main():

    print("=" * 70)
    print("SALESFORGE — OPPORTUNITY DETECTION ENGINE V2")
    print("=" * 70)

    df = pd.read_csv(FEATURES)

    print(f"Feature rows loaded: {len(df):,}")

    opportunities = []

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
                    "opportunity_type": opportunity[
                        "opportunity_type"
                    ],
                    "score": opportunity["score"],
                    "priority": opportunity["priority"],
                    "evidence": json.dumps(
                        opportunity["evidence"]
                    ),
                    "recommended_action": opportunity[
                        "recommended_action"
                    ],
                    "status": "OPEN",
                }
            )

    opportunities_df = pd.DataFrame(opportunities)

    output = OUTPUT_DIR / "opportunities_v2.csv"

    opportunities_df.to_csv(
        output,
        index=False,
    )

    print("\n" + "=" * 70)
    print("RESULT")
    print("=" * 70)

    print(
        f"Opportunities detected: "
        f"{len(opportunities_df):,}"
    )

    if len(opportunities_df) == 0:
        print("No opportunities detected.")
        return

    print("\nBy opportunity type:")

    print(
        opportunities_df[
            "opportunity_type"
        ]
        .value_counts()
        .to_string()
    )

    print("\nBy priority:")

    print(
        opportunities_df[
            "priority"
        ]
        .value_counts()
        .to_string()
    )

    print("\nScore distribution:")

    print(
        opportunities_df["score"]
        .describe()
        .to_string()
    )

    print("\nTop 15 opportunities:")

    print(
        opportunities_df[
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
        .to_string(index=False)
    )

    print("\nExample highest-priority opportunity:")

    top = opportunities_df.sort_values(
        "score",
        ascending=False,
    ).iloc[0]

    print(f"\n{top['opportunity_id']}")
    print(f"Outlet: {top['outlet_name']}")
    print(f"Type: {top['opportunity_type']}")
    print(f"Score: {top['score']}")
    print(f"Priority: {top['priority']}")
    print(
        "Evidence:",
        json.loads(top["evidence"]),
    )
    print(
        "Action:",
        top["recommended_action"],
    )

    print(f"\nSaved to: {output}")
    print("\nOpportunity detection V2 complete.")


if __name__ == "__main__":
    main()