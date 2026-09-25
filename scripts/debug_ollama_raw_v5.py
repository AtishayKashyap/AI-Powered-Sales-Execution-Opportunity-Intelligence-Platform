import json
from pathlib import Path

from ai.prompts import build_prompt
from ai.provider_adapter import OllamaProvider


PROJECT_ROOT = Path(__file__).resolve().parents[1]

INPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed_v5"
    / "ai_explanation_inputs_v5.jsonl"
)


def load_opportunity(opportunity_id: str):
    with INPUT_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue

            opportunity = json.loads(line)

            if opportunity.get("opportunity_id") == opportunity_id:
                return opportunity

    raise ValueError(f"{opportunity_id} not found")


def main():
    opportunity = load_opportunity("OPP-000187")

    provider = OllamaProvider(model="qwen3:8b")

    prompt = build_prompt(opportunity)

    print("=" * 80)
    print("INPUT EVIDENCE")
    print("=" * 80)

    print(
        json.dumps(
            opportunity["evidence"],
            indent=2,
            ensure_ascii=False,
        )
    )

    print("\n" + "=" * 80)
    print("RAW QWEN3 OUTPUT")
    print("=" * 80)

    result = provider.generate_json(prompt)

    print(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
    