#!/usr/bin/env python3
"""
SalesForge — V5 Opportunity Quality Analysis

Analyzes detected opportunities against the V5 planted benchmark without
changing the detector. The goal is to understand score/evidence distributions
among planted and unplanted opportunities before calibration.

Outputs:
  data/processed_v5/quality_analysis_v5.csv
  data/processed_v5/quality_analysis_examples_v5.csv
"""

from pathlib import Path
import json
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OPP = ROOT / "data" / "processed_v5" / "opportunities_v5.csv"
GT = ROOT / "data" / "generated_v5" / "scenario_ground_truth.csv"
OUT_DIR = ROOT / "data" / "processed_v5"

SCORE_BINS = [-np.inf, 59.999, 69.999, 79.999, 89.999, np.inf]
SCORE_LABELS = ["<60", "60-69", "70-79", "80-89", "90+"]


def load_data():
    opp = pd.read_csv(OPP)
    gt = pd.read_csv(GT)

    # Ground truth format is scenario columns keyed by outlet_id.
    scenario_cols = [
        c for c in [
            "revenue_decline_scenario",
            "inactive_scenario",
            "stock_risk_scenario",
            "cross_sell_scenario",
        ] if c in gt.columns
    ]

    if not scenario_cols:
        raise ValueError("No scenario columns found in ground truth.")

    rows = []
    for _, r in gt.iterrows():
        outlet_id = int(r["outlet_id"])
        for col in scenario_cols:
            if bool(r[col]):
                rows.append({
                    "outlet_id": outlet_id,
                    "scenario_type": {
                        "revenue_decline_scenario": "Revenue Recovery",
                        "inactive_scenario": "Inactive Outlet",
                        "stock_risk_scenario": "Stock Risk",
                        "cross_sell_scenario": "Cross-Sell",
                    }[col]
                })

    planted = pd.DataFrame(rows)
    return opp, planted


def parse_evidence(x):
    try:
        return json.loads(x) if isinstance(x, str) else {}
    except Exception:
        return {}


def enrich(opp, planted):
    planted = planted.copy()
    planted["key"] = (
        planted["outlet_id"].astype(str) + "|" + planted["scenario_type"]
    )

    opp = opp.copy()
    opp["key"] = (
        opp["outlet_id"].astype(str) + "|" + opp["opportunity_type"]
    )
    opp["is_planted"] = opp["key"].isin(set(planted["key"]))

    evidence = opp["evidence"].apply(parse_evidence)
    ev = pd.json_normalize(evidence)
    ev.index = opp.index

    # Preserve evidence fields even when absent for a type.
    for col in ev.columns:
        safe = f"ev_{col}"
        opp[safe] = ev[col]

    opp["score_bucket"] = pd.cut(
        opp["score"],
        bins=SCORE_BINS,
        labels=SCORE_LABELS,
        include_lowest=True,
    )

    return opp


def numeric_summary(df, col):
    if col not in df.columns:
        return None
    s = pd.to_numeric(df[col], errors="coerce").dropna()
    if s.empty:
        return None
    return {
        "mean": round(float(s.mean()), 3),
        "median": round(float(s.median()), 3),
        "p25": round(float(s.quantile(.25)), 3),
        "p75": round(float(s.quantile(.75)), 3),
        "min": round(float(s.min()), 3),
        "max": round(float(s.max()), 3),
    }


def print_score_analysis(df):
    print("\n" + "=" * 78)
    print("SCORE / PLANTED VS UNPLANTED ANALYSIS")
    print("=" * 78)

    table = (
        df.groupby(["opportunity_type", "score_bucket", "is_planted"],
                   observed=False)
          .size()
          .reset_index(name="count")
    )

    for typ in df["opportunity_type"].unique():
        print(f"\n{typ}")
        sub = table[table["opportunity_type"] == typ]
        pivot = sub.pivot_table(
            index="score_bucket",
            columns="is_planted",
            values="count",
            aggfunc="sum",
            fill_value=0,
        )
        pivot = pivot.rename(columns={True: "planted", False: "unplanted"})
        for c in ["planted", "unplanted"]:
            if c not in pivot.columns:
                pivot[c] = 0
        pivot["total"] = pivot["planted"] + pivot["unplanted"]
        pivot["planted_pct"] = np.where(
            pivot["total"] > 0,
            100 * pivot["planted"] / pivot["total"],
            0,
        ).round(2)
        print(pivot[["planted", "unplanted", "total", "planted_pct"]].to_string())


def print_evidence_analysis(df):
    print("\n" + "=" * 78)
    print("EVIDENCE DISTRIBUTIONS")
    print("=" * 78)

    # These names mirror the actual JSON keys emitted by
    # detect_opportunities_v5.py.
    evidence_candidates = {
        "Revenue Recovery": [
            "ev_revenue_previous_30d",
            "ev_revenue_30d",
            "ev_revenue_growth_30d",
            "ev_revenue_gap_vs_previous_30d",
            "ev_orders_previous_30d",
            "ev_orders_30d",
            "ev_revenue_index_vs_peer",
        ],
        "Inactive Outlet": [
            "ev_revenue_previous_30d",
            "ev_days_since_last_order",
            "ev_revenue_30d",
            "ev_orders_previous_30d",
            "ev_orders_30d",
        ],
        "Stock Risk": [
            "ev_stockout_events_90d",
            "ev_stockout_rate_90d",
            "ev_avg_closing_stock_90d",
        ],
        "Cross-Sell": [
            "ev_territory_category_rank",
            "ev_territory_category_orders_90d",
            "ev_current_category_count_90d",
        ],
    }

    for typ, cols in evidence_candidates.items():
        print(f"\n--- {typ} ---")
        sub = df[df["opportunity_type"] == typ]
        for planted_flag, label in [(True, "PLANTED"), (False, "UNPLANTED")]:
            s = sub[sub["is_planted"] == planted_flag]
            print(f"{label}: n={len(s)}")
            for col in cols:
                result = numeric_summary(s, col)
                if result:
                    print(f"  {col.replace('ev_', '')}: {result}")


def build_summary(df):
    rows = []
    for (typ, bucket, planted), sub in df.groupby(
        ["opportunity_type", "score_bucket", "is_planted"],
        observed=False,
    ):
        rows.append({
            "opportunity_type": typ,
            "score_bucket": str(bucket),
            "planted": bool(planted),
            "count": int(len(sub)),
            "score_mean": round(float(sub["score"].mean()), 3) if len(sub) else np.nan,
            "score_median": round(float(sub["score"].median()), 3) if len(sub) else np.nan,
        })

    return pd.DataFrame(rows)


def build_examples(df):
    # Show highest-scoring unplanted examples and lowest-scoring planted examples.
    frames = []
    for typ in df["opportunity_type"].unique():
        sub = df[df["opportunity_type"] == typ]

        unplanted = sub[~sub["is_planted"]].sort_values(
            "score", ascending=False
        ).head(10).copy()
        unplanted["example_group"] = "high_score_unplanted"

        planted = sub[sub["is_planted"]].sort_values(
            "score", ascending=True
        ).head(10).copy()
        planted["example_group"] = "low_score_planted"

        frames.extend([unplanted, planted])

    if not frames:
        return pd.DataFrame()

    out = pd.concat(frames, ignore_index=True)

    keep = [
        "example_group", "opportunity_id", "outlet_id",
        "opportunity_type", "score", "priority",
        "evidence", "recommended_action",
    ]
    return out[[c for c in keep if c in out.columns]]


def main():
    print("SALESFORGE — V5 OPPORTUNITY QUALITY ANALYSIS")
    print("=" * 78)
    print(f"Opportunities: {OPP}")
    print(f"Ground truth:  {GT}")

    opp, planted = load_data()
    df = enrich(opp, planted)

    print(f"\nDetected opportunities: {len(df):,}")
    print(f"Planted benchmark opportunities: {len(planted):,}")
    print(f"Planted detected: {int(df['is_planted'].sum()):,}")
    print(f"Unplanted detections: {int((~df['is_planted']).sum()):,}")

    print_score_analysis(df)
    print_evidence_analysis(df)

    summary = build_summary(df)
    examples = build_examples(df)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    summary_path = OUT_DIR / "quality_analysis_v5.csv"
    examples_path = OUT_DIR / "quality_analysis_examples_v5.csv"
    summary.to_csv(summary_path, index=False)
    examples.to_csv(examples_path, index=False)

    print("\n" + "=" * 78)
    print("OUTPUTS")
    print("=" * 78)
    print(summary_path)
    print(examples_path)
    print("\nV5 opportunity quality analysis complete.")


if __name__ == "__main__":
    main()
