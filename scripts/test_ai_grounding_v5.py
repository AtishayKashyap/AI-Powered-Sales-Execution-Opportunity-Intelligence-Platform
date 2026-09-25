"""
Validate SalesForge's generated fallback explanations against
the real V5 AI evidence inputs.

This does NOT call an LLM.
It verifies that the existing deterministic explanations
pass the same grounding layer that future LLM outputs will use.
"""

import ast
import csv
import json
from pathlib import Path

from ai.validate import validate_grounding


INPUT_PATH = Path(
    "data/processed_v5/ai_explanation_inputs_v5.jsonl"
)

FALLBACK_PATH = Path(
    "data/processed_v5/ai_explanations_fallback_v5.csv"
)


def load_inputs():
    records = {}

    with INPUT_PATH.open(
        "r",
        encoding="utf-8",
    ) as f:
        for line in f:
            if line.strip():
                record = json.loads(line)
                records[record["opportunity_id"]] = record

    return records


def load_fallbacks():
    records = {}

    with FALLBACK_PATH.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as f:
        reader = csv.DictReader(f)

        for row in reader:
            records[row["opportunity_id"]] = row

    return records


def build_payload(row):
    return {
        "summary": row["summary"],
        "why_it_matters": row["why_it_matters"],
        "recommended_action": row["recommended_action"],
        "evidence_used": ast.literal_eval(
            row["evidence_used"]
        ),
        "confidence": row["confidence"],
    }


def main():
    inputs = load_inputs()
    fallbacks = load_fallbacks()

    print(
        f"Loaded AI inputs: {len(inputs)}"
    )

    print(
        f"Loaded fallback explanations: {len(fallbacks)}"
    )

    passed = 0
    failed = 0

    for opportunity_id, opportunity in inputs.items():

        if opportunity_id not in fallbacks:
            print(
                f"[FAIL] {opportunity_id}: "
                "missing fallback explanation"
            )
            failed += 1
            continue

        row = fallbacks[opportunity_id]

        payload = build_payload(row)

        try:
            validate_grounding(
                payload,
                opportunity["evidence"],
            )

            passed += 1

            print(
                f"[PASS] {opportunity_id} | "
                f"{opportunity['opportunity_type']}"
            )

        except Exception as exc:
            failed += 1

            print(
                f"[FAIL] {opportunity_id} | "
                f"{opportunity['opportunity_type']} | "
                f"{exc}"
            )

    print()
    print("=" * 60)
    print("SALESFORGE AI GROUNDING TEST")
    print("=" * 60)
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Total:  {passed + failed}")

    if failed:
        raise SystemExit(1)

    print()
    print("All real V5 explanations passed grounding validation.")


if __name__ == "__main__":
    main()