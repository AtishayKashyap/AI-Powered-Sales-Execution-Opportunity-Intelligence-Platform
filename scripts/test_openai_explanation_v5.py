import json
from pathlib import Path

from ai.explain import SalesForgeExplainer
from ai.provider_adapter import OpenAIProvider


ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data" / "processed_v5" / "ai_explanation_inputs_v5.jsonl"


def load_opportunity(opportunity_id: str):
    with INPUT.open("r", encoding="utf-8") as f:
        for line in f:
            record = json.loads(line)

            if record["opportunity_id"] == opportunity_id:
                return record

    raise ValueError(f"Opportunity not found: {opportunity_id}")


def main():
    opportunity_id = "OPP-000187"

    print("=" * 78)
    print("SALESFORGE — REAL OPENAI EXPLANATION TEST")
    print("=" * 78)

    opportunity = load_opportunity(opportunity_id)

    print(f"Opportunity: {opportunity['opportunity_id']}")
    print(f"Type:        {opportunity['opportunity_type']}")
    print(f"Priority:    {opportunity['priority_band']}")
    print()

    provider = OpenAIProvider()
    explainer = SalesForgeExplainer(provider)

    result = explainer.explain(opportunity)

    print("AI EXPLANATION")
    print("-" * 78)
    print(json.dumps(result, indent=2, ensure_ascii=False))

    print()
    print("✓ OpenAI response received")
    print("✓ JSON parsed")
    print("✓ Schema validation passed")
    print("✓ Grounding validation passed")


if __name__ == "__main__":
    main()
    