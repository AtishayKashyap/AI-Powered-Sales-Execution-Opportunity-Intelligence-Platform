from pathlib import Path
import json
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]

OPPORTUNITIES = (
    ROOT
    / "data"
    / "processed_v4"
    / "opportunities_v4.csv"
)

GROUND_TRUTH = (
    ROOT
    / "data"
    / "generated_v4"
    / "scenario_ground_truth.csv"
)

OUTPUT_DIR = ROOT / "data" / "processed_v4"


# Map SalesForge opportunity types to the corresponding
# planted scenario in the synthetic dataset.
SCENARIO_MAP = {
    "REVENUE_RECOVERY": "revenue_decline_scenario",
    "INACTIVE_OUTLET": "inactive_scenario",
    "STOCK_RISK": "stock_risk_scenario",
}


def evaluate_type(
    opportunities,
    ground_truth,
    opportunity_type,
    scenario_column,
):
    """
    Evaluate one opportunity type at outlet level.

    An outlet counts as detected if at least one opportunity
    of the relevant type was generated for it.
    """

    planted = set(
        ground_truth.loc[
            ground_truth[scenario_column] == 1,
            "outlet_id",
        ]
    )

    detected = set(
        opportunities.loc[
            opportunities["opportunity_type"]
            == opportunity_type,
            "outlet_id",
        ]
    )

    true_positive = planted & detected
    false_positive = detected - planted
    false_negative = planted - detected

    tp = len(true_positive)
    fp = len(false_positive)
    fn = len(false_negative)

    precision = (
        tp / (tp + fp)
        if (tp + fp) > 0
        else 0
    )

    recall = (
        tp / (tp + fn)
        if (tp + fn) > 0
        else 0
    )

    f1 = (
        2 * precision * recall
        / (precision + recall)
        if (precision + recall) > 0
        else 0
    )

    return {
        "opportunity_type": opportunity_type,
        "scenario": scenario_column,
        "planted": len(planted),
        "detected": len(detected),
        "true_positive": tp,
        "false_positive": fp,
        "false_negative": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "tp_outlets": sorted(true_positive),
        "fp_outlets": sorted(false_positive),
        "fn_outlets": sorted(false_negative),
    }


def main():

    print("=" * 70)
    print("SALESFORGE — OPPORTUNITY ENGINE EVALUATION")
    print("=" * 70)

    opportunities = pd.read_csv(OPPORTUNITIES)
    ground_truth = pd.read_csv(GROUND_TRUTH)

    print(
        f"Opportunity rows: {len(opportunities):,}"
    )

    print(
        f"Ground-truth rows: {len(ground_truth):,}"
    )

    results = []

    # ------------------------------------------------------------
    # Evaluate each supported scenario
    # ------------------------------------------------------------

    for opportunity_type, scenario_column in SCENARIO_MAP.items():

        result = evaluate_type(
            opportunities,
            ground_truth,
            opportunity_type,
            scenario_column,
        )

        results.append(result)

    results_df = pd.DataFrame(
        [
            {
                key: value
                for key, value in result.items()
                if key
                not in {
                    "tp_outlets",
                    "fp_outlets",
                    "fn_outlets",
                }
            }
            for result in results
        ]
    )

    # ------------------------------------------------------------
    # Print summary
    # ------------------------------------------------------------

    print("\n" + "=" * 70)
    print("EVALUATION SUMMARY")
    print("=" * 70)

    display_df = results_df.copy()

    for column in [
        "precision",
        "recall",
        "f1",
    ]:
        display_df[column] = (
            display_df[column] * 100
        ).round(2).astype(str) + "%"

    print(
        display_df.to_string(
            index=False
        )
    )

    # ------------------------------------------------------------
    # Overall detection statistics
    # ------------------------------------------------------------

    valid_results = results_df[
        results_df["detected"] > 0
    ]

    total_planted = (
        valid_results["planted"].sum()
    )

    total_detected = (
        valid_results["detected"].sum()
    )

    total_tp = (
        valid_results["true_positive"].sum()
    )

    total_fp = (
        valid_results["false_positive"].sum()
    )

    total_fn = (
        valid_results["false_negative"].sum()
    )

    overall_precision = (
        total_tp / (total_tp + total_fp)
        if total_tp + total_fp > 0
        else 0
    )

    overall_recall = (
        total_tp / (total_tp + total_fn)
        if total_tp + total_fn > 0
        else 0
    )

    print("\n" + "=" * 70)
    print("OVERALL")
    print("=" * 70)

    print(
        f"Planted opportunities : {total_planted:,}"
    )

    print(
        f"Detected opportunities: {total_detected:,}"
    )

    print(
        f"True positives        : {total_tp:,}"
    )

    print(
        f"False positives       : {total_fp:,}"
    )

    print(
        f"False negatives       : {total_fn:,}"
    )

    print(
        f"Precision             : "
        f"{overall_precision * 100:.2f}%"
    )

    print(
        f"Recall                : "
        f"{overall_recall * 100:.2f}%"
    )

    # ------------------------------------------------------------
    # Priority analysis
    # ------------------------------------------------------------

    print("\n" + "=" * 70)
    print("PRIORITY ANALYSIS")
    print("=" * 70)

    for priority in [
        "HIGH",
        "MEDIUM",
        "LOW",
    ]:

        subset = opportunities[
            opportunities["priority"]
            == priority
        ]

        print(
            f"{priority:<10}"
            f"{len(subset):>8,}"
        )

    # ------------------------------------------------------------
    # Ground-truth overlap
    # ------------------------------------------------------------

    all_planted = set()

    for scenario_column in SCENARIO_MAP.values():

        planted = set(
            ground_truth.loc[
                ground_truth[scenario_column] == 1,
                "outlet_id",
            ]
        )

        all_planted.update(planted)

    all_detected = set(
        opportunities["outlet_id"]
    )

    planted_detected_overlap = (
        all_planted & all_detected
    )

    print("\n" + "=" * 70)
    print("OVERALL OUTLET OVERLAP")
    print("=" * 70)

    print(
        f"Unique planted outlets : "
        f"{len(all_planted):,}"
    )

    print(
        f"Unique detected outlets: "
        f"{len(all_detected):,}"
    )

    print(
        f"Planted + detected     : "
        f"{len(planted_detected_overlap):,}"
    )

    # ------------------------------------------------------------
    # Save detailed JSON
    # ------------------------------------------------------------

    detailed = []

    for result in results:

        detailed.append(
            {
                "opportunity_type":
                    result["opportunity_type"],

                "scenario":
                    result["scenario"],

                "planted":
                    result["planted"],

                "detected":
                    result["detected"],

                "true_positive":
                    result["true_positive"],

                "false_positive":
                    result["false_positive"],

                "false_negative":
                    result["false_negative"],

                "precision":
                    result["precision"],

                "recall":
                    result["recall"],

                "f1":
                    result["f1"],

                "tp_outlets":
                    result["tp_outlets"],

                "fp_outlets":
                    result["fp_outlets"],

                "fn_outlets":
                    result["fn_outlets"],
            }
        )

    output = (
        OUTPUT_DIR
        / "opportunity_evaluation.json"
    )

    with open(
        output,
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            detailed,
            f,
            indent=2,
        )

    print(
        f"\nDetailed evaluation saved to:\n"
        f"{output}"
    )

    print(
        "\nEvaluation complete."
    )


if __name__ == "__main__":
    main()