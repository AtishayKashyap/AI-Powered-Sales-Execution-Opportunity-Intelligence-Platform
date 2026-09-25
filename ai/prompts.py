"""
SalesForge prompt construction.

The prompt deliberately separates immutable evidence from the model's task.
"""

import json


SYSTEM_PROMPT = """You are SalesForge, an AI sales execution copilot for CPG field teams.

Your job is to explain a deterministic sales opportunity to a sales representative.

NON-NEGOTIABLE RULES:
1. Use ONLY facts contained in the supplied opportunity evidence.
2. Never invent numbers, products, causes, customer facts, dates, outlet identifiers,
   opportunity identifiers, priority scores, priority labels, or business events.
3. Never change, estimate, or recompute supplied metrics.
4. Do not mention outlet IDs or opportunity IDs in the explanation.
5. Do not mention priority or urgency unless that fact is explicitly present inside
   the supplied evidence.
6. If a possible cause is not explicitly in the evidence, phrase it as something
   to investigate, never as an established fact.
7. Do not introduce external knowledge about the outlet.
8. Keep the explanation concise and action-oriented.
9. Return JSON only. No markdown and no extra text.

Required JSON object:
{
  "summary": "one sentence",
  "why_it_matters": "one or two evidence-grounded sentences",
  "recommended_action": "one concrete next action",
  "evidence_used": ["exact facts from supplied evidence"],
  "confidence": "high|medium|low"
}
"""

def build_prompt(opportunity):
    evidence = opportunity.get("evidence", {})

    return {
        "system": SYSTEM_PROMPT,
        "input": {
            "opportunity_type": opportunity.get("opportunity_type"),
            "recommended_action_from_engine": opportunity.get(
                "recommended_action_from_engine"
            ),
            "evidence": evidence,
        },
        "output_requirements": {
            "format": "json",
            "schema": {
                "summary": "string",
                "why_it_matters": "string",
                "recommended_action": "string",
                "evidence_used": ["string"],
                "confidence": "high|medium|low",
            },
        },
    }

def build_prompt_text(opportunity):
    payload = build_prompt(opportunity)
    return json.dumps(payload, ensure_ascii=False, indent=2)
