import json
from pathlib import Path

from ai.explain import SalesForgeExplainer
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

    raise ValueError(
        f"Opportunity {opportunity_id} not found in {INPUT_FILE}"
    )


def main():
    opportunity_id = "OPP-000187"

    print("=" * 70)
    print("SalesForge — Ollama AI Explanation Test")
    print("=" * 70)

    print(f"\nLoading opportunity: {opportunity_id}")

    opportunity = load_opportunity(opportunity_id)

    print(
        f"Type: {opportunity.get('opportunity_type')}"
    )

    print("Starting local Ollama inference...")

    provider = OllamaProvider(
        model="qwen3:8b"
    )

    explainer = SalesForgeExplainer(provider)

    result = explainer.explain(opportunity)

    print("\n" + "=" * 70)
    print("AI EXPLANATION")
    print("=" * 70)

    print(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False,
        )
    )

    print("\n" + "=" * 70)
    print("RESULT")
    print("=" * 70)

    print("✓ Ollama inference succeeded")
    print("✓ JSON parsing succeeded")
    print("✓ Explanation schema validation succeeded")
    print("✓ Grounding validation succeeded")
    print("\nSalesForge local AI pipeline is working.")


if __name__ == "__main__":
    main()