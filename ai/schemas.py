"""
SalesForge AI output schemas.

The deterministic engine owns the facts.
The AI layer owns only the wording.
"""

from dataclasses import dataclass, asdict
from typing import List
import json


@dataclass
class Explanation:
    summary: str
    why_it_matters: str
    recommended_action: str
    evidence_used: List[str]
    confidence: str

    def validate(self):
        if not isinstance(self.summary, str) or not self.summary.strip():
            raise ValueError("summary cannot be empty")

        if (
            not isinstance(self.why_it_matters, str)
            or not self.why_it_matters.strip()
        ):
            raise ValueError("why_it_matters cannot be empty")

        if (
            not isinstance(self.recommended_action, str)
            or not self.recommended_action.strip()
        ):
            raise ValueError("recommended_action cannot be empty")

        if self.confidence not in {"high", "medium", "low"}:
            raise ValueError(
                "confidence must be high, medium, or low"
            )

        if not isinstance(self.evidence_used, list):
            raise ValueError("evidence_used must be a list")

        if not self.evidence_used:
            raise ValueError(
                "evidence_used must contain at least one item"
            )

        if not all(
            isinstance(item, str) and item.strip()
            for item in self.evidence_used
        ):
            raise ValueError(
                "evidence_used must contain non-empty strings"
            )

        return self

    def to_dict(self):
        return asdict(self)

    def to_json(self):
        self.validate()

        return json.dumps(
            self.to_dict(),
            ensure_ascii=False,
        )


def validate_explanation(payload):
    if not isinstance(payload, dict):
        raise ValueError(
            "AI response must be a JSON object"
        )

    required = {
        "summary",
        "why_it_matters",
        "recommended_action",
        "evidence_used",
        "confidence",
    }

    missing = required - set(payload)

    if missing:
        raise ValueError(
            f"Missing fields: {sorted(missing)}"
        )

    return Explanation(
        summary=str(payload["summary"]),
        why_it_matters=str(payload["why_it_matters"]),
        recommended_action=str(
            payload["recommended_action"]
        ),
        evidence_used=payload["evidence_used"],
        confidence=str(
            payload["confidence"]
        ).lower(),
    ).validate()