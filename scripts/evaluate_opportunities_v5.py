#!/usr/bin/env python3
"""
SalesForge — V5 Opportunity Evaluation

Evaluates the deterministic V5 opportunity detector against the controlled
scenario ground truth. The detector itself never reads this ground truth;
this script is evaluation-only.

Outputs:
  data/processed_v5/evaluation_v5_metrics.csv
  data/processed_v5/evaluation_v5_missed.csv
  data/processed_v5/evaluation_v5_true_positives.csv

Definitions:
  TP = planted scenario + matching detected opportunity type on the same outlet
  FP = detected opportunity whose outlet/type is not planted for that type
  FN = planted outlet/type with no matching detection

Cross-sell is evaluated at two levels:
  1. outlet/type detection (primary benchmark)
  2. target-category match for true positives (diagnostic)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
GROUND_TRUTH = ROOT / "data" / "generated_v5" / "scenario_ground_truth.csv"
OPPORTUNITIES = ROOT / "data" / "processed_v5" / "opportunities_v5.csv"
OUT_DIR = ROOT / "data" / "processed_v5"

SCENARIOS = {
    "revenue_decline_scenario": "Revenue Recovery",
    "inactive_scenario": "Inactive Outlet",
    "stock_risk_scenario": "Stock Risk",
    "cross_sell_scenario": "Cross-Sell",
}


def parse_evidence(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if pd.isna(value):
        return {}
    try:
        parsed = json.loads(str(value))
        return parsed if isinstance(parsed, dict) else {}
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}


def validate_inputs(truth: pd.DataFrame, opportunities: pd.DataFrame) -> None:
    required_truth = {"outlet_id", *SCENARIOS.keys()}
    required_opp = {
        "opportunity_id",
        "outlet_id",
        "opportunity_type",
        "score",
        "priority",
        "evidence",
    }

    missing_truth = required_truth - set(truth.columns)
    missing_opp = required_opp - set(opportunities.columns)

    if missing_truth:
        raise ValueError(f"Ground truth missing columns: {sorted(missing_truth)}")
    if missing_opp:
        raise ValueError(f"Opportunity output missing columns: {sorted(missing_opp)}")

    if truth["outlet_id"].duplicated().any():
        raise ValueError("Ground truth contains duplicate outlet_id values.")
    if opportunities["opportunity_id"].duplicated().any():
        raise ValueError("Opportunity output contains duplicate opportunity_id values.")


def evaluate_type(
    truth: pd.DataFrame,
    opportunities: pd.DataFrame,
    scenario_column: str,
    opportunity_type: str,
) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame]:
    planted_ids = set(
        truth.loc[truth[scenario_column].astype(int) == 1, "outlet_id"].astype(str)
    )

    detected = opportunities[
        opportunities["opportunity_type"].eq(opportunity_type)
    ].copy()
    detected["outlet_id_str"] = detected["outlet_id"].astype(str)
    detected["is_true_positive"] = detected["outlet_id_str"].isin(planted_ids)

    detected_ids = set(detected["outlet_id_str"])
    tp_ids = planted_ids & detected_ids
    fn_ids = planted_ids - detected_ids

    tp = len(tp_ids)
    fp = int((~detected["is_true_positive"]).sum())
    fn = len(fn_ids)
    planted = len(planted_ids)
    detected_count = len(detected)

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0

    # True-positive score/priority diagnostics.
    tp_rows = detected[detected["is_true_positive"]].copy()
    tp_scores = tp_rows["score"].astype(float)

    metrics = {
        "scenario": scenario_column,
        "opportunity_type": opportunity_type,
        "planted": planted,
        "detected": detected_count,
        "true_positive": tp,
        "false_positive": fp,
        "false_negative": fn,
        "detection_rate_pct": round(100 * tp / planted, 2) if planted else 0.0,
        "precision_pct": round(100 * precision, 2),
        "recall_pct": round(100 * recall, 2),
        "f1_pct": round(100 * f1, 2),
        "tp_score_mean": round(float(tp_scores.mean()), 2) if len(tp_scores) else None,
        "tp_score_min": round(float(tp_scores.min()), 2) if len(tp_scores) else None,
        "tp_score_median": round(float(tp_scores.median()), 2) if len(tp_scores) else None,
        "tp_score_max": round(float(tp_scores.max()), 2) if len(tp_scores) else None,
        "tp_high": int((tp_rows["priority"] == "HIGH").sum()),
        "tp_medium": int((tp_rows["priority"] == "MEDIUM").sum()),
        "tp_low": int((tp_rows["priority"] == "LOW").sum()),
    }

    missed = pd.DataFrame(
        {
            "scenario": scenario_column,
            "opportunity_type": opportunity_type,
            "outlet_id": sorted(fn_ids),
        }
    )

    if not missed.empty:
        # Bring useful feature-independent truth fields along.
        truth_subset = truth[["outlet_id"]].copy()
        truth_subset["outlet_id"] = truth_subset["outlet_id"].astype(str)
        missed = missed.merge(truth_subset, on="outlet_id", how="left")

    tp_rows = tp_rows.drop(columns=["outlet_id_str", "is_true_positive"], errors="ignore")
    tp_rows.insert(0, "evaluation_scenario", scenario_column)
    tp_rows.insert(1, "evaluation_type", opportunity_type)

    return metrics, missed, tp_rows


def evaluate_cross_sell_category(
    truth: pd.DataFrame,
    opportunities: pd.DataFrame,
) -> dict[str, Any]:
    planted = truth.loc[
        truth["cross_sell_scenario"].astype(int) == 1,
        ["outlet_id", "cross_sell_category"],
    ].copy()
    planted["outlet_id"] = planted["outlet_id"].astype(str)
    planted["cross_sell_category"] = planted["cross_sell_category"].fillna("").astype(str)

    detected = opportunities[
        opportunities["opportunity_type"].eq("Cross-Sell")
    ].copy()
    detected["outlet_id"] = detected["outlet_id"].astype(str)
    detected["detected_target_category"] = detected["evidence"].map(
        lambda x: parse_evidence(x).get("target_category", "")
    ).fillna("").astype(str)

    tp = detected.merge(planted, on="outlet_id", how="inner")
    if tp.empty:
        exact = 0
    else:
        exact = int(
            (tp["detected_target_category"] == tp["cross_sell_category"]).sum()
        )

    return {
        "cross_sell_planted_outlets": int(len(planted)),
        "cross_sell_detected_planted_outlets": int(len(tp)),
        "cross_sell_exact_category_matches": exact,
        "cross_sell_category_accuracy_pct": round(
            100 * exact / len(tp), 2
        ) if len(tp) else 0.0,
    }


def print_section(title: str) -> None:
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def main() -> None:
    print("=" * 78)
    print("SALESFORGE — V5 OPPORTUNITY EVALUATION")
    print("=" * 78)
    print(f"Ground truth:  {GROUND_TRUTH}")
    print(f"Opportunities: {OPPORTUNITIES}")

    if not GROUND_TRUTH.exists():
        raise FileNotFoundError(f"Ground truth not found: {GROUND_TRUTH}")
    if not OPPORTUNITIES.exists():
        raise FileNotFoundError(f"Opportunity output not found: {OPPORTUNITIES}")

    truth = pd.read_csv(GROUND_TRUTH)
    opportunities = pd.read_csv(OPPORTUNITIES)
    validate_inputs(truth, opportunities)

    # Normalize IDs for reliable matching while preserving original output columns.
    truth["outlet_id"] = truth["outlet_id"].astype(str)
    opportunities["outlet_id"] = opportunities["outlet_id"].astype(str)

    print(f"\nGround-truth outlets: {len(truth):,}")
    print(f"Detected opportunities: {len(opportunities):,}")

    metrics_rows = []
    missed_rows = []
    tp_rows = []

    for scenario_column, opportunity_type in SCENARIOS.items():
        metrics, missed, tp = evaluate_type(
            truth,
            opportunities,
            scenario_column,
            opportunity_type,
        )
        metrics_rows.append(metrics)
        if not missed.empty:
            missed_rows.append(missed)
        if not tp.empty:
            tp_rows.append(tp)

    metrics_df = pd.DataFrame(metrics_rows)

    # Overall micro metrics across the four independent planted scenario/type pairs.
    total_tp = int(metrics_df["true_positive"].sum())
    total_fp = int(metrics_df["false_positive"].sum())
    total_fn = int(metrics_df["false_negative"].sum())
    total_planted = int(metrics_df["planted"].sum())
    total_detected = int(metrics_df["detected"].sum())
    micro_precision = total_tp / (total_tp + total_fp) if total_tp + total_fp else 0.0
    micro_recall = total_tp / (total_tp + total_fn) if total_tp + total_fn else 0.0
    micro_f1 = (
        2 * micro_precision * micro_recall / (micro_precision + micro_recall)
        if micro_precision + micro_recall else 0.0
    )

    overall = {
        "scenario": "OVERALL_MICRO",
        "opportunity_type": "All Types",
        "planted": total_planted,
        "detected": total_detected,
        "true_positive": total_tp,
        "false_positive": total_fp,
        "false_negative": total_fn,
        "detection_rate_pct": round(100 * total_tp / total_planted, 2),
        "precision_pct": round(100 * micro_precision, 2),
        "recall_pct": round(100 * micro_recall, 2),
        "f1_pct": round(100 * micro_f1, 2),
        "tp_score_mean": None,
        "tp_score_min": None,
        "tp_score_median": None,
        "tp_score_max": None,
        "tp_high": int(metrics_df["tp_high"].sum()),
        "tp_medium": int(metrics_df["tp_medium"].sum()),
        "tp_low": int(metrics_df["tp_low"].sum()),
    }
    metrics_df = pd.concat([metrics_df, pd.DataFrame([overall])], ignore_index=True)

    missed_df = (
        pd.concat(missed_rows, ignore_index=True)
        if missed_rows
        else pd.DataFrame(columns=["scenario", "opportunity_type", "outlet_id"])
    )
    tp_df = (
        pd.concat(tp_rows, ignore_index=True)
        if tp_rows
        else pd.DataFrame()
    )

    category_metrics = evaluate_cross_sell_category(truth, opportunities)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    metrics_path = OUT_DIR / "evaluation_v5_metrics.csv"
    missed_path = OUT_DIR / "evaluation_v5_missed.csv"
    tp_path = OUT_DIR / "evaluation_v5_true_positives.csv"

    metrics_df.to_csv(metrics_path, index=False)
    missed_df.to_csv(missed_path, index=False)
    tp_df.to_csv(tp_path, index=False)

    print_section("TYPE-LEVEL BENCHMARK")
    display_cols = [
        "opportunity_type",
        "planted",
        "detected",
        "true_positive",
        "false_positive",
        "false_negative",
        "precision_pct",
        "recall_pct",
        "f1_pct",
    ]
    print(metrics_df[display_cols].to_string(index=False))

    print_section("TRUE-POSITIVE SCORE / PRIORITY")
    score_cols = [
        "opportunity_type",
        "tp_score_mean",
        "tp_score_min",
        "tp_score_median",
        "tp_score_max",
        "tp_high",
        "tp_medium",
        "tp_low",
    ]
    print(metrics_df[metrics_df["scenario"] != "OVERALL_MICRO"][score_cols].to_string(index=False))

    print_section("CROSS-SELL CATEGORY DIAGNOSTIC")
    for key, value in category_metrics.items():
        print(f"{key}: {value}")

    print_section("MISSED PLANTED OPPORTUNITIES")
    print(f"Total missed: {len(missed_df):,}")
    if not missed_df.empty:
        print(missed_df.groupby("opportunity_type").size().to_string())
        print("\nFirst 30 missed outlet/type pairs:")
        print(missed_df.head(30).to_string(index=False))
    else:
        print("None.")

    print_section("OUTPUTS")
    print(metrics_path)
    print(missed_path)
    print(tp_path)
    print("\nV5 opportunity evaluation complete.")


if __name__ == "__main__":
    main()
