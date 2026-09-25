#!/usr/bin/env python3
"""
SalesForge — V5 AI Opportunity Explanation Layer

Provider-neutral AI layer. It prepares a strict structured-output prompt from
deterministic SalesForge evidence. The LLM is explicitly forbidden from inventing
or recalculating business facts.

This script works without an API key and produces:
  data/processed_v5/ai_explanation_inputs_v5.jsonl

It also writes a deterministic fallback explanation for every top action so
the pipeline remains demonstrable without an external model.

When an LLM provider is connected later, feed the prompt + evidence to the
provider and validate its JSON response against the schema below.
"""

from pathlib import Path
import json
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data" / "processed_v5" / "top_actions_v5.csv"
OUTPUT = ROOT / "data" / "processed_v5" / "ai_explanation_inputs_v5.jsonl"
FALLBACK = ROOT / "data" / "processed_v5" / "ai_explanations_fallback_v5.csv"

SYSTEM_PROMPT = """You are SalesForge, a sales execution copilot for CPG field teams.
Explain a deterministic sales opportunity using ONLY the supplied evidence.

Rules:
1. Never invent numbers, products, causes, customer facts, dates, or claims.
2. Never change or recompute the supplied metrics.
3. If a cause is not present in evidence, describe it as something to investigate,
   not as an established cause.
4. Keep the explanation concise and action-oriented.
5. Return valid JSON only using the requested schema.

JSON schema:
{
  "summary": "one sentence",
  "why_it_matters": "one or two sentences grounded in evidence",
  "recommended_action": "one concrete next action",
  "evidence_used": ["exact supplied facts/metrics used"],
  "confidence": "high|medium|low"
}
"""


def parse_evidence(x):
    try:
        return json.loads(x) if isinstance(x, str) else {}
    except Exception:
        return {}


def fmt_money(x):
    return f"₹{float(x):,.0f}"


def fallback(row):
    typ = row["opportunity_type"]
    ev = parse_evidence(row["evidence"])

    if typ == "Revenue Recovery":
        prev = ev["revenue_previous_30d"]
        cur = ev["revenue_30d"]
        growth = ev["revenue_growth_30d"] * 100
        gap = ev["revenue_gap_vs_previous_30d"]
        op = ev["orders_previous_30d"]
        oc = ev["orders_30d"]
        peer = ev["revenue_index_vs_peer"] * 100
        return {
            "summary": f"Revenue recovery opportunity with a {abs(growth):.1f}% decline in recent revenue.",
            "why_it_matters": (
                f"Revenue fell from {fmt_money(prev)} to {fmt_money(cur)}, "
                f"an estimated {fmt_money(gap)} gap; recent revenue is "
                f"{peer:.1f}% of the peer benchmark."
            ),
            "recommended_action": (
                "Prioritize a recovery visit and investigate lost demand, "
                "ordering frequency, or distribution issues."
            ),
            "evidence_used": [
                f"Previous 30d revenue: {fmt_money(prev)}",
                f"Recent 30d revenue: {fmt_money(cur)}",
                f"Revenue decline: {growth:.1f}%",
                f"Revenue gap: {fmt_money(gap)}",
                f"Orders: {int(op)} → {int(oc)}",
                f"Peer revenue index: {ev['revenue_index_vs_peer']:.3f}",
            ],
            "confidence": "high",
        }

    if typ == "Inactive Outlet":
        prev = ev["revenue_previous_30d"]
        days = ev["days_since_last_order"]

        # This is the deterministic rule used by the
        # opportunity detector:
        # days_since_last_order > 30
        inactivity_threshold = 30

        return {
            "summary": (
                f"Inactive outlet with no recent orders for "
                f"{int(days)} days."
            ),
            "why_it_matters": (
                f"The outlet previously generated {fmt_money(prev)} in the "
                "previous 30-day period but currently has no orders."
            ),
            "recommended_action": (
                "Prioritize a win-back contact and investigate "
                "the reason for inactivity."
            ),
            "evidence_used": [
                f"Previous 30d revenue: {fmt_money(prev)}",
                f"Days since last order: {int(days)}",
                f"Inactivity threshold: {inactivity_threshold} days",
                f"Current 30d revenue: {fmt_money(ev['revenue_30d'])}",
                f"Previous orders: {int(ev['orders_previous_30d'])}",
            ],
            "confidence": "high",
        }

    if typ == "Stock Risk":
        events = ev["stockout_events_90d"]
        rate = ev["stockout_rate_90d"] * 100
        stock = ev["avg_closing_stock_90d"]
        return {
            "summary": f"Stock-risk opportunity with {int(events)} stockout events in the last 90 days.",
            "why_it_matters": (
                f"Stockouts occurred in {rate:.1f}% of inventory snapshots and "
                f"average closing stock was {stock:.2f}."
            ),
            "recommended_action": (
                "Prioritize replenishment review and verify the outlet's current stock position."
            ),
            "evidence_used": [
                f"Stockout events: {int(events)}",
                f"Stockout rate: {rate:.1f}%",
                f"Average closing stock: {stock:.2f}",
            ],
            "confidence": "high",
        }

    if typ == "Cross-Sell":
        cat = ev["target_category"]
        rank = ev["territory_category_rank"]
        orders = ev["territory_category_orders_90d"]
        current = ev["current_category_count_90d"]
        return {
            "summary": f"Cross-sell opportunity for {cat}.",
            "why_it_matters": (
                f"{cat} ranks #{int(rank)} in territory category demand with "
                f"{int(orders):,} orders in the last 90 days, while the outlet "
                f"currently carries {int(current)} categories in its observed assortment."
            ),
            "recommended_action": (
                f"Evaluate introducing {cat} at the outlet and validate shelf space and demand."
            ),
            "evidence_used": [
                f"Target category: {cat}",
                f"Territory category rank: #{int(rank)}",
                f"Territory category orders (90d): {int(orders):,}",
                f"Current category count (90d): {int(current)}",
            ],
            "confidence": "high",
        }

    return {
        "summary": f"{typ} opportunity detected.",
        "why_it_matters": "Review the supplied opportunity evidence.",
        "recommended_action": row.get("recommended_action", "Review opportunity."),
        "evidence_used": [],
        "confidence": "medium",
    }


def main():
    print("SALESFORGE — V5 AI EXPLANATION PREPARATION")
    print("=" * 78)

    if not INPUT.exists():
        raise FileNotFoundError(f"Missing top actions: {INPUT}")

    df = pd.read_csv(INPUT)
    records = []
    fallbacks = []

    for _, row in df.iterrows():
        evidence = parse_evidence(row["evidence"])

        if row["opportunity_type"] == "Inactive Outlet":
            evidence["inactivity_threshold_days"] = 30

        payload = {
            "opportunity_id": row["opportunity_id"],
            "outlet_id": int(row["outlet_id"]),
            "opportunity_type": row["opportunity_type"],
            "priority_score": float(row["priority_score"]),
            "priority_band": row["priority_band"],
            "recommended_action_from_engine": row["recommended_action"],
            "evidence": evidence,
            "system_prompt": SYSTEM_PROMPT,
            "output_schema": {
                "summary": "string",
                "why_it_matters": "string",
                "recommended_action": "string",
                "evidence_used": ["string"],
                "confidence": "high|medium|low",
            },
        }
        records.append(payload)

        result = fallback(row)
        fallbacks.append({
            "selection_rank": row["selection_rank"],
            "opportunity_id": row["opportunity_id"],
            "outlet_id": row["outlet_id"],
            "opportunity_type": row["opportunity_type"],
            "priority_score": row["priority_score"],
            "priority_band": row["priority_band"],
            **result,
        })

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    pd.DataFrame(fallbacks).to_csv(FALLBACK, index=False)

    print(f"Top actions processed: {len(df):,}")
    print(f"AI prompt/input file: {OUTPUT}")
    print(f"Deterministic fallback explanations: {FALLBACK}")
    print("\nAI explanation preparation complete.")


if __name__ == "__main__":
    main()
