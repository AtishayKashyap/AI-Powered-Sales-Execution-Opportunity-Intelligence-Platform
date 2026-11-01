from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from .conftest import make_client


def test_health(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok", "llm": "none"}


def test_queue_is_ranked_mixed_and_one_per_outlet(client: TestClient) -> None:
    queue = client.get("/opportunities/queue").json()
    assert [o["queue_rank"] for o in queue] == list(range(1, len(queue) + 1))
    assert len({o["outlet"]["outlet_id"] for o in queue}) == len(queue)
    assert len({o["opportunity_type"] for o in queue}) >= 3
    assert all(o["status"] == "open" for o in queue)


def test_list_filters_and_paginates(client: TestClient) -> None:
    page = client.get("/opportunities", params={"opportunity_type": "Stock Risk", "limit": 5}).json()
    assert page["total"] >= len(page["items"]) and len(page["items"]) <= 5
    assert {o["opportunity_type"] for o in page["items"]} == {"Stock Risk"}
    scores = [o["priority_score"] for o in page["items"]]
    assert scores == sorted(scores, reverse=True)
    second = client.get("/opportunities", params={"opportunity_type": "Stock Risk", "limit": 5, "offset": 5}).json()
    assert not {o["opportunity_id"] for o in page["items"]} & {o["opportunity_id"] for o in second["items"]}


def test_search_by_outlet_name(client: TestClient) -> None:
    name = client.get("/opportunities/queue").json()[0]["outlet"]["outlet_name"]
    hits = client.get("/opportunities", params={"q": name.split()[0].lower()}).json()["items"]
    assert hits and all(name.split()[0] in h["outlet"]["outlet_name"] for h in hits)


def test_invalid_input_is_rejected(client: TestClient) -> None:
    assert client.get("/opportunities", params={"priority_band": "P9"}).status_code == 422
    assert client.get("/opportunities", params={"limit": 1000}).status_code == 422
    oid = client.get("/opportunities/queue").json()[0]["opportunity_id"]
    assert client.post(f"/opportunities/{oid}/actions", json={"action_type": "teleport"}).status_code == 422
    assert (
        client.post(f"/opportunities/{oid}/actions", json={"action_type": "visit", "note": "x" * 1001}).status_code
        == 422
    )
    assert client.get("/opportunities/OPP-99999").status_code == 404
    assert client.put("/actions/999999/outcome", json={"outcome": "resolved"}).status_code == 404


def test_action_and_outcome_lifecycle(client: TestClient) -> None:
    oid = client.get("/opportunities/queue").json()[0]["opportunity_id"]
    detail = client.post(f"/opportunities/{oid}/actions", json={"action_type": "visit", "note": "met owner"})
    assert detail.status_code == 201
    body = detail.json()
    assert body["status"] == "in_progress"
    assert body["actions"][0]["rep_id"] == body["outlet"]["rep"]["rep_id"]  # assigned to the outlet's rep
    action_id = body["actions"][0]["action_id"]

    assert client.put(f"/actions/{action_id}/outcome", json={"outcome": "follow_up"}).json()["status"] == "in_progress"
    assert client.put(f"/actions/{action_id}/outcome", json={"outcome": "resolved"}).json()["status"] == "resolved"
    assert client.get("/opportunities", params={"status": "resolved"}).json()["total"] == 1


def test_recording_an_outcome_twice_does_not_double_count(client: TestClient) -> None:
    oid = client.get("/opportunities/queue").json()[1]["opportunity_id"]
    action_id = client.post(f"/opportunities/{oid}/actions", json={"action_type": "call"}).json()["actions"][0][
        "action_id"
    ]
    for _ in range(3):
        client.put(f"/actions/{action_id}/outcome", json={"outcome": "resolved"})
    summary = client.get("/analytics/summary").json()
    assert summary["actioned"] == 1 and summary["resolved"] == 1
    assert summary["by_outcome"] == {"resolved": 1}
    assert summary["resolution_rate"] == 1.0


def test_latest_action_decides_status(client: TestClient) -> None:
    oid = client.get("/opportunities/queue").json()[2]["opportunity_id"]
    first = client.post(f"/opportunities/{oid}/actions", json={"action_type": "visit"}).json()["actions"][0][
        "action_id"
    ]
    client.put(f"/actions/{first}/outcome", json={"outcome": "no_response"})
    second = client.post(f"/opportunities/{oid}/actions", json={"action_type": "call"}).json()["actions"][-1][
        "action_id"
    ]
    assert client.put(f"/actions/{second}/outcome", json={"outcome": "not_viable"}).json()["status"] == "closed"


def test_analytics_totals_match_the_data(client: TestClient, db: Session) -> None:
    from salesforge import models

    s = client.get("/analytics/summary").json()
    assert s["opportunities"] == db.query(models.Opportunity).count()
    assert s["queue_size"] == 20
    assert sum(t["opportunities"] for t in s["by_type"]) == s["opportunities"]
    assert s["resolution_rate"] is None and s["top_reps"] == []


def test_explanation_falls_back_to_rules_without_a_model(client: TestClient) -> None:
    oid = client.get("/opportunities/queue").json()[0]["opportunity_id"]
    e = client.get(f"/opportunities/{oid}/explanation").json()
    assert e["source"] == "rule_based" and e["model"] is None and "rules" in e["note"]


def test_write_endpoints_are_rate_limited(engine: Engine, db: Session) -> None:
    limited = make_client(engine, writes_per_minute=2)
    oid = limited.get("/opportunities/queue").json()[0]["opportunity_id"]
    codes = [limited.post(f"/opportunities/{oid}/actions", json={"action_type": "call"}).status_code for _ in range(3)]
    assert codes == [201, 201, 429]
    assert limited.get("/opportunities/queue").status_code == 200  # reads are not limited
