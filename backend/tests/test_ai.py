from __future__ import annotations

import json

import httpx
import pytest
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from salesforge import models
from salesforge.ai import rule_based
from salesforge.ai.grounding import check, extract_claims
from salesforge.ai.providers import OllamaProvider, OpenAICompatibleProvider, ProviderError
from salesforge.ai.schema import ExplanationDraft

from .conftest import first_queue_item, make_client

CROSS_SELL = {
    "orders_90d": 17,
    "peer_adoption_pct": 96.1,
    "peer_median_monthly_revenue": 3114,
    "peer_outlets": 76,
    "target_category": "Personal Care",
}
REVENUE = {
    "revenue_60d": 14663,
    "expected_revenue_60d": 119139,
    "revenue_change_pct": -87.7,
    "orders_60d": 5,
    "scheduled_visits_60d": 26,
    "expected_orders_60d": 20.7,
}


def draft(
    summary: str,
    why: str = "Most similar outlets carry it.",
    action: str = "Introduce it on the next visit.",
    used: list[str] | None = None,
) -> ExplanationDraft:
    return ExplanationDraft(
        summary=summary, why_it_matters=why, recommended_action=action, evidence_used=used or ["peer_adoption_pct"]
    )


# ----------------------------------------------------------------------------- grounding


def test_grounded_explanation_passes() -> None:
    d = draft(
        "This outlet does not stock Personal Care yet.",
        "96.1% of 76 similar outlets carry it, with a median of ₹3,114 a month each.",
        used=["peer_adoption_pct", "peer_outlets", "peer_median_monthly_revenue"],
    )
    assert check(d, CROSS_SELL).ok


@pytest.mark.parametrize(
    "summary",
    [
        "Snacks sales grew 3x and the outlet has 7 competitors nearby.",  # invented category, ratio and count
        "Offer a 5 percent discount to secure the listing quickly.",  # invented percentage
        "Similar outlets earn ₹9,000 a month from Personal Care.",  # wrong money value
        "Seven in ten similar outlets carry Personal Care already.",  # number words are checked too
        "Peer adoption is 96.1 and revenue is 76% higher than average.",  # right number, wrong unit
        "Adoption doubled among similar outlets in the last quarter.",  # unsupported multiplier word
    ],
)
def test_ungrounded_claims_are_rejected(summary: str) -> None:
    assert not check(draft(summary), CROSS_SELL).ok


def test_evidence_used_must_name_real_fields() -> None:
    result = check(draft("This outlet does not stock Personal Care.", used=["Snacks are popular"]), CROSS_SELL)
    assert not result.ok and "do not exist" in result.problems[0]


def test_rounding_percent_changes_and_windows_are_allowed() -> None:
    d = draft(
        "Sales over the last 60 days are about 88% below normal.",
        "5 orders from 26 visits brought in ₹14.7k against roughly ₹119,139 expected, about an eighth.",
        used=["revenue_change_pct", "orders_60d"],
    )
    assert check(d, REVENUE).ok, check(d, REVENUE).problems


def test_claim_extraction_reads_units() -> None:
    units = {c.text: c.unit for c in extract_claims("down 55% to ₹12.4k, half of Rs 22,096 over 60 days, 3x")}
    assert units == {
        "55%": "percent",
        "₹12.4k": "money",
        "half": "multiplier",
        "Rs 22,096": "money",
        "60": "plain",
        "3x": "multiplier",
    }


@pytest.mark.parametrize("otype", [t.value for t in models.OpportunityType])
def test_rule_based_explanations_always_pass_grounding(db: Session, otype: str) -> None:
    opportunities = db.query(models.Opportunity).filter(models.Opportunity.opportunity_type == otype).all()
    assert opportunities
    for o in opportunities:
        result = check(rule_based.explain(otype, o.evidence), o.evidence)
        assert result.ok, (o.opportunity_id, result.problems)


# ----------------------------------------------------------------------------- explainer


class FakeProvider:
    model = "fake-model"

    def __init__(self, *answers: object) -> None:
        self.answers = list(answers)
        self.calls: list[list[dict[str, str]]] = []

    def complete_json(self, messages: list[dict[str, str]]) -> dict[str, object]:
        self.calls.append(list(messages))
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        assert isinstance(answer, dict)
        return answer


def grounded_for(o: models.Opportunity) -> dict[str, object]:
    return rule_based.explain(o.opportunity_type.value, o.evidence).model_dump()


def test_valid_llm_answer_is_served_and_cached(engine: Engine, db: Session) -> None:
    o = first_queue_item(db)
    provider = FakeProvider(grounded_for(o))
    client = make_client(engine, provider)
    first = client.get(f"/opportunities/{o.opportunity_id}/explanation").json()
    second = client.get(f"/opportunities/{o.opportunity_id}/explanation").json()
    assert first["source"] == second["source"] == "llm" and first["model"] == "fake-model"
    assert len(provider.calls) == 1  # second request came from the cache


def test_ungrounded_answer_gets_one_retry_with_the_problems(engine: Engine, db: Session) -> None:
    o = first_queue_item(db)
    bad = {**grounded_for(o), "summary": "Revenue fell 99% after a competitor opened next door."}
    provider = FakeProvider(bad, grounded_for(o))
    e = make_client(engine, provider).get(f"/opportunities/{o.opportunity_id}/explanation").json()
    assert e["source"] == "llm"
    assert "failed validation" in provider.calls[1][-1]["content"] and "99%" in provider.calls[1][-1]["content"]


def test_persistently_ungrounded_answer_falls_back_to_rules(engine: Engine, db: Session) -> None:
    o = first_queue_item(db)
    bad = {**grounded_for(o), "why_it_matters": "Sales doubled last year in this city."}
    e = make_client(engine, FakeProvider(bad, bad)).get(f"/opportunities/{o.opportunity_id}/explanation").json()
    assert e["source"] == "rule_based" and "did not pass" in e["note"]
    assert db.get(models.Explanation, o.opportunity_id) is None  # rejected answers are never cached


def test_provider_failure_or_malformed_json_falls_back(engine: Engine, db: Session) -> None:
    o = first_queue_item(db)
    for answers in ((ProviderError("timeout"),), ({"summary": "too short"}, {"nothing": 1})):
        e = make_client(engine, FakeProvider(*answers)).get(f"/opportunities/{o.opportunity_id}/explanation").json()
        assert e["source"] == "rule_based"


# ----------------------------------------------------------------------------- providers (HTTP mocked)

GOOD = {
    "summary": "No order for 40 days from a regular outlet.",
    "why_it_matters": "It used to order often.",
    "recommended_action": "Make a win-back visit this week.",
    "evidence_used": ["days_since_last_order"],
}


def test_openai_compatible_provider_sends_json_mode_and_parses() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        content = "```json\n" + json.dumps(GOOD) + "\n```"
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    p = OpenAICompatibleProvider(
        "https://llm.test/v1", "k", "m", 5, client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    assert p.complete_json([{"role": "user", "content": "x"}]) == GOOD
    assert seen["response_format"] == {"type": "json_object"} and seen["model"] == "m"


def test_ollama_provider_sends_the_schema() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert json.loads(request.content)["format"]["required"]
        return httpx.Response(200, json={"message": {"content": json.dumps(GOOD)}})

    p = OllamaProvider("http://ollama.test", "qwen3:8b", 5, client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert p.complete_json([{"role": "user", "content": "x"}]) == GOOD


@pytest.mark.parametrize(
    "response", [httpx.Response(500), httpx.Response(200, json={"choices": [{"message": {"content": "not json"}}]})]
)
def test_provider_errors_are_normalised(response: httpx.Response) -> None:
    p = OpenAICompatibleProvider(
        "https://llm.test/v1", "k", "m", 5, client=httpx.Client(transport=httpx.MockTransport(lambda r: response))
    )
    with pytest.raises(ProviderError):
        p.complete_json([{"role": "user", "content": "x"}])
