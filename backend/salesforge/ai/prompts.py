"""Prompt for turning an opportunity's evidence into a short explanation for a field rep."""

from __future__ import annotations

import json

SYSTEM_PROMPT = """You explain sales opportunities to field sales reps of a consumer-goods distributor.
Each opportunity was found by a rule engine; you only explain it in plain language.

Rules:
- Use only the facts in "evidence". Do not add numbers, products, causes, competitors or events.
- Every number you write must be one of the evidence values (you may round it, show it as a percentage,
  or write a ratio of two evidence values). Money is in Indian rupees, written like ₹12,400.
- Mention a product category only if it is the evidence's target_category.
- If a cause is unknown, say what the rep should find out, not what happened.
- No outlet or opportunity ids. Be brief and concrete.
- "evidence_used" lists the evidence field names (keys) you relied on.

Reply with one JSON object and nothing else:
{"summary": "one sentence", "why_it_matters": "one or two sentences",
 "recommended_action": "one concrete next step", "evidence_used": ["field_name", ...]}"""


def user_message(opportunity_type: str, evidence: dict[str, object], engine_action: str, outlet: dict[str, str]) -> str:
    return json.dumps(
        {
            "opportunity_type": opportunity_type,
            "outlet": outlet,
            "evidence": evidence,
            "engine_recommended_action": engine_action,
        },
        ensure_ascii=False,
    )


def retry_message(problems: list[str]) -> str:
    return (
        "Your answer failed validation: "
        + "; ".join(problems)
        + ". Rewrite it using only the evidence values, and reply with the JSON object only."
    )
