from pathlib import Path
import json
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

FEATURES = (
    ROOT
    / "data"
    / "processed_v2"
    / "outlet_features.csv"
)

OUTPUT_DIR = ROOT / "data" / "processed_v2"

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


def revenue_recovery(row):

    growth = row["revenue_growth_30d"]
    gap = row["revenue_gap_vs_previous_30d"]
    previous_revenue = row["revenue_previous_30d"]
    order_growth = row["order_frequency_growth_30d"]
    peer_gap = row["revenue_growth_gap_vs_peer"]

    if previous_revenue < 1000:
        return None

    if pd.isna(growth):
        return None

    # Core detection condition.
    if not (
        growth <= -0.30
        and gap >= 1000
    ):
        return None

    evidence = [
        f"Revenue declined {abs(growth) * 100:.1f}% "
        f"vs previous 30d",
        f"Revenue gap of ₹{gap:,.0f}",
    ]

    score = 50

    # Business impact.
    if gap >= 10000:
        score += 25
    elif gap >= 5000:
        score += 20
    elif gap >= 2000:
        score += 10

    # Severe deterioration.
    if growth <= -0.60:
        score += 15
    elif growth <= -0.45:
        score += 10

    # Corroborating signal.
    if pd.notna(order_growth) and order_growth <= -0.25:
        score += 10
        evidence.append(
            f"Order frequency declined "
            f"{abs(order_growth) * 100:.1f}%"
        )

    # Peer evidence.
    if pd.notna(peer_gap) and peer_gap <= -0.25:
        evidence.append(
            "Revenue growth materially below peer benchmark"
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


def inactive_outlet(row):

    days = row["days_since_last_order"]
    previous_revenue = row["revenue_previous_30d"]

    if previous_revenue < 1000:
        return None

    if days < 45:
        return None

    evidence = [
        f"No order for {days:.0f} days",
        f"Previous 30d revenue was ₹{previous_revenue:,.0f}",
    ]

    if days >= 75:
        score = 95
        priority = "HIGH"
    elif days >= 60:
        score = 80
        priority = "HIGH"
    else:
        score = 60
        priority = "MEDIUM"

    if row["revenue_30d"] == 0:
        score = min(score + 5, 100)
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


def stock_risk(row):

    events = row["stockout_events_90d"]
    rate = row["stockout_rate_90d"]
    closing_stock = row["avg_closing_stock_90d"]

    if events < 2:
        return None

    evidence = [
        f"{events:.0f} stockout events in last 90d",
    ]

    score = 65

    if events >= 4:
        score += 20
    elif events >= 3:
        score += 10

    if rate >= 0.05:
        score += 10
        evidence.append(
            f"Stockout rate: {rate * 100:.2f}%"
        )

    if closing_stock <= 1:
        score += 5
        evidence.append(
            f"Average closing stock: "
            f"{closing_stock:.1f} units"
        )

    score = min(score, 100)

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


def main():

    print("=" * 70)
    print("SALESFORGE — OPPORTUNITY ENGINE V3")
    print("=" * 70)

    df = pd.read_csv(FEATURES)

    print(
        f"Feature rows loaded: {len(df):,}"
    )

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

    result = pd.DataFrame(opportunities)

    output = (
        OUTPUT_DIR
        / "opportunities_v3.csv"
    )

    result.to_csv(
        output,
        index=False,
    )

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
            .to_string(index=False)
        )

        top = result.sort_values(
            "score",
            ascending=False,
        ).iloc[0]

        print("\nExample:")
        print(
            f"Outlet: {top['outlet_name']}"
        )
        print(
            f"Type: {top['opportunity_type']}"
        )
        print(
            f"Score: {top['score']}"
        )
        print(
            f"Priority: {top['priority']}"
        )
        print(
            "Evidence:",
            json.loads(top["evidence"]),
        )

    print(
        f"\nSaved to: {output}"
    )

    print(
        "\nOpportunity Engine V3 complete."
    )


if __name__ == "__main__":
    main()