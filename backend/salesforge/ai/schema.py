"""The structured output every explanation must have, LLM or rule-based."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ExplanationDraft(BaseModel):
    summary: str = Field(min_length=10, max_length=240)
    why_it_matters: str = Field(min_length=10, max_length=500)
    recommended_action: str = Field(min_length=10, max_length=300)
    evidence_used: list[str] = Field(min_length=1, max_length=8, description="Evidence field names that were cited")

    @property
    def text_fields(self) -> list[str]:
        return [self.summary, self.why_it_matters, self.recommended_action]


class Explanation(ExplanationDraft):
    source: Literal["llm", "rule_based"]
    model: str | None = None
    note: str | None = None


JSON_SCHEMA: dict[str, object] = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "why_it_matters": {"type": "string"},
        "recommended_action": {"type": "string"},
        "evidence_used": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["summary", "why_it_matters", "recommended_action", "evidence_used"],
}
