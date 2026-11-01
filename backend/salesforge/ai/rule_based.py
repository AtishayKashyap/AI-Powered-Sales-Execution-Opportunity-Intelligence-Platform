"""Deterministic explanations from templates. Used when no LLM is configured or its answer fails validation.
Every number comes straight from the evidence, so these always pass the grounding check (tested)."""

from __future__ import annotations

from .schema import ExplanationDraft


def _num(value: object) -> float:
    if not isinstance(value, int | float):
        raise TypeError(f"expected a number, got {value!r}")
    return float(value)


def rupees(value: object) -> str:
    return f"₹{_num(value):,.0f}"


def explain(opportunity_type: str, e: dict[str, object]) -> ExplanationDraft:
    if opportunity_type == "Revenue Recovery":
        return ExplanationDraft(
            summary=f"Sales over the last 60 days are {abs(_num(e['revenue_change_pct'])):.0f}% below this outlet's "
            "normal level.",
            why_it_matters=(
                f"It ordered {e['orders_60d']} times from {e['scheduled_visits_60d']} scheduled visits against "
                f"about {e['expected_orders_60d']} expected, bringing in {rupees(e['revenue_60d'])} instead of "
                f"roughly {rupees(e['expected_revenue_60d'])}."
            ),
            recommended_action="Visit, find out which categories stopped selling and agree a recovery order.",
            evidence_used=[
                "revenue_change_pct",
                "orders_60d",
                "expected_orders_60d",
                "revenue_60d",
                "expected_revenue_60d",
            ],
        )
    if opportunity_type == "Inactive Outlet":
        return ExplanationDraft(
            summary=f"No order for {e['days_since_last_order']} days from an outlet that used to order regularly.",
            why_it_matters=(
                f"It averaged {e['baseline_monthly_orders']} orders and {rupees(e['baseline_monthly_revenue'])} "
                "a month before it went quiet."
            ),
            recommended_action="Make a win-back visit, ask why ordering stopped and reorder from its usual mix.",
            evidence_used=["days_since_last_order", "baseline_monthly_orders", "baseline_monthly_revenue"],
        )
    if opportunity_type == "Stock Risk":
        return ExplanationDraft(
            summary=f"Shelves ran empty on {e['stockout_days_90d']} of the last 90 days.",
            why_it_matters=(
                f"A {e['stockout_rate_pct']}% stock-out rate on an outlet worth "
                f"{rupees(e['baseline_monthly_revenue'])} a month means sales are lost while the shelf is empty."
            ),
            recommended_action="Raise replenishment with the distributor and agree a higher safety stock.",
            evidence_used=["stockout_days_90d", "stockout_rate_pct", "baseline_monthly_revenue"],
        )
    if opportunity_type == "Cross-Sell":
        return ExplanationDraft(
            summary=f"This outlet does not stock {e['target_category']}, unlike most similar outlets nearby.",
            why_it_matters=(
                f"{e['peer_adoption_pct']}% of {e['peer_outlets']} comparable outlets carry it, selling a median of "
                f"{rupees(e['peer_median_monthly_revenue'])} a month."
            ),
            recommended_action=f"Introduce {e['target_category']} on the next visit with a small trial order.",
            evidence_used=["target_category", "peer_adoption_pct", "peer_outlets", "peer_median_monthly_revenue"],
        )
    raise ValueError(f"unknown opportunity type: {opportunity_type}")
