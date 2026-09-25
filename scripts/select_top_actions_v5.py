#!/usr/bin/env python3
"""
SalesForge — V5 Top Action Selection (Priority-First)

Builds an operational top-action queue from the frozen prioritization layer.

Rules:
- Original priority_score is never changed.
- Never select the same outlet twice.
- Hard caps prevent one opportunity type from dominating the queue.
- Cross-Sell target categories have a soft cap only when alternatives exist.
- Among eligible candidates, highest original priority_score wins.
- Ground truth is never used.
"""

from pathlib import Path
import json
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data" / "processed_v5" / "prioritized_opportunities_v5.csv"
OUTPUT = ROOT / "data" / "processed_v5" / "top_actions_v5.csv"

TOP_N = 20
TYPE_CAPS = {
    "Revenue Recovery": 7,
    "Inactive Outlet": 5,
    "Stock Risk": 5,
    "Cross-Sell": 5,
}
CROSS_SELL_CATEGORY_CAP = 4


def parse_evidence(x):
    try:
        return json.loads(x) if isinstance(x, str) else {}
    except Exception:
        return {}


def main():
    print("SALESFORGE — V5 TOP ACTION SELECTION")
    print("=" * 78)

    if not INPUT.exists():
        raise FileNotFoundError(f"Missing prioritized opportunities: {INPUT}")

    df = pd.read_csv(INPUT)
    required = {"outlet_id", "opportunity_type", "priority_score", "evidence"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    df["priority_score"] = pd.to_numeric(
        df["priority_score"], errors="coerce"
    ).fillna(0.0)

    # Highest original priority first. This ordering is preserved whenever
    # the candidate is eligible under the hard diversity constraints.
    df = df.sort_values(
        ["priority_score", "score", "opportunity_id"],
        ascending=[False, False, True],
        kind="stable",
    ).reset_index(drop=True)

    selected = []
    selected_outlets = set()
    type_counts = {k: 0 for k in TYPE_CAPS}
    category_counts = {}

    # First pass: enforce type caps and unique outlets. Cross-Sell category
    # cap is enforced only if enough eligible alternatives exist.
    remaining = df.copy()

    while len(selected) < min(TOP_N, len(df)) and not remaining.empty:
        eligible = remaining[
            ~remaining["outlet_id"].isin(selected_outlets)
            & remaining["opportunity_type"].map(
                lambda x: type_counts.get(x, 0) < TYPE_CAPS.get(x, TOP_N)
            )
        ].copy()

        if eligible.empty:
            break

        # Prefer highest priority. For Cross-Sell, avoid a category cap when
        # there is an alternative candidate at the same stage; never alter
        # the stored score.
        chosen = None
        for idx, row in eligible.iterrows():
            if row["opportunity_type"] != "Cross-Sell":
                chosen = row
                break

            category = parse_evidence(row["evidence"]).get("target_category")
            count = category_counts.get(category, 0)

            if count < CROSS_SELL_CATEGORY_CAP:
                chosen = row
                break

            # If this candidate's category is saturated, look for an eligible
            # Cross-Sell alternative with an unsaturated category.
            alt = eligible[
                eligible["opportunity_type"].eq("Cross-Sell")
                & eligible["evidence"].apply(
                    lambda x: category_counts.get(
                        parse_evidence(x).get("target_category"), 0
                    ) < CROSS_SELL_CATEGORY_CAP
                )
            ]
            if not alt.empty:
                chosen = alt.iloc[0]
            else:
                # No unsaturated category exists; keep priority-first behavior.
                chosen = row
            break

        if chosen is None:
            break

        selected.append(chosen.copy())
        selected_outlets.add(chosen["outlet_id"])

        typ = chosen["opportunity_type"]
        type_counts[typ] = type_counts.get(typ, 0) + 1

        if typ == "Cross-Sell":
            category = parse_evidence(chosen["evidence"]).get("target_category")
            category_counts[category] = category_counts.get(category, 0) + 1

        remaining = remaining.drop(index=chosen.name)

    top = pd.DataFrame(selected).reset_index(drop=True)
    if top.empty:
        raise RuntimeError("No top actions were selected.")

    top.insert(0, "selection_rank", range(1, len(top) + 1))
    top["queue_reason"] = "Selected by highest original priority score within diversity constraints."

    front = [
        "selection_rank", "opportunity_id", "outlet_id",
        "opportunity_type", "priority_score", "priority_band",
        "action_urgency", "queue_reason", "evidence",
        "recommended_action",
    ]
    top = top[[c for c in front if c in top.columns] +
              [c for c in top.columns if c not in front]]

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    top.to_csv(OUTPUT, index=False)

    print(f"\nInput opportunities: {len(df):,}")
    print(f"Top actions selected: {len(top):,}")
    print(f"Unique outlets: {top['outlet_id'].nunique():,}")

    print("\n" + "=" * 78)
    print("TYPE MIX")
    print("=" * 78)
    print(top["opportunity_type"].value_counts().to_string())

    print("\n" + "=" * 78)
    print("TOP ACTION QUEUE")
    print("=" * 78)
    print(top[
        ["selection_rank", "outlet_id", "opportunity_type",
         "priority_score", "priority_band", "evidence"]
    ].to_string(index=False))

    print("\n" + "=" * 78)
    print("OUTPUT")
    print("=" * 78)
    print(OUTPUT)
    print("\nV5 priority-first top action selection complete.")


if __name__ == "__main__":
    main()
