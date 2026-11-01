"""Explanation service: cached LLM answer -> fresh LLM answer (validated, one retry) -> rule-based fallback."""

from __future__ import annotations

import json
import logging

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from .. import models
from . import prompts, rule_based
from .grounding import check
from .providers import Provider, ProviderError
from .schema import Explanation, ExplanationDraft

log = logging.getLogger(__name__)


def _outlet_context(o: models.Opportunity) -> dict[str, str]:
    return {"type": o.outlet.outlet_type, "tier": o.outlet.tier, "city": o.outlet.city}


def ask_llm(provider: Provider, o: models.Opportunity) -> tuple[ExplanationDraft | None, list[str]]:
    messages = [
        {"role": "system", "content": prompts.SYSTEM_PROMPT},
        {
            "role": "user",
            "content": prompts.user_message(
                o.opportunity_type.value, o.evidence, o.recommended_action, _outlet_context(o)
            ),
        },
    ]
    problems: list[str] = []
    for _attempt in range(2):
        try:
            raw = provider.complete_json(messages)
            draft = ExplanationDraft.model_validate(raw)
        except ProviderError as exc:
            return None, [str(exc)]
        except ValidationError as exc:
            problems = [f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors()]
        else:
            result = check(draft, o.evidence)
            if result.ok:
                return draft, []
            problems = result.problems
        messages += [
            {"role": "assistant", "content": json.dumps(raw, ensure_ascii=False)},
            {"role": "user", "content": prompts.retry_message(problems)},
        ]
    return None, problems


def get_explanation(db: Session, o: models.Opportunity, provider: Provider | None) -> Explanation:
    cached = db.scalar(select(models.Explanation).where(models.Explanation.opportunity_id == o.opportunity_id))
    if cached is not None:
        return Explanation(
            summary=cached.summary,
            why_it_matters=cached.why_it_matters,
            recommended_action=cached.recommended_action,
            evidence_used=cached.evidence_used,
            source="llm",
            model=cached.model,
        )

    note = "No language model is configured; this summary is generated from the evidence by rules."
    if provider is not None:
        draft, problems = ask_llm(provider, o)
        if draft is not None:
            stmt = (
                pg_insert(models.Explanation)
                .values(
                    opportunity_id=o.opportunity_id,
                    summary=draft.summary,
                    why_it_matters=draft.why_it_matters,
                    recommended_action=draft.recommended_action,
                    evidence_used=draft.evidence_used,
                    model=provider.model,
                )
                .on_conflict_do_nothing(index_elements=["opportunity_id"])
            )
            db.execute(stmt)
            db.commit()
            return Explanation(**draft.model_dump(), source="llm", model=provider.model)
        log.warning("LLM explanation rejected for %s: %s", o.opportunity_id, problems)
        note = "The language model's answer did not pass the evidence check, so a rule-based summary is shown."

    draft = rule_based.explain(o.opportunity_type.value, o.evidence)
    return Explanation(**draft.model_dump(), source="rule_based", note=note)
