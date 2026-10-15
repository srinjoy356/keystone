"""API guardrails: input validation, per-visitor rate limit behind a proxy, unknown tenants, no LLM calls needed."""
from fastapi.testclient import TestClient
from keystone import api

c = TestClient(api.app)


def test_bad_inputs_are_rejected_before_any_work():
    assert c.post("/api/ask", json={"question": "hi", "user": "x y"}).status_code == 422
    assert c.post("/api/ask", json={"question": "a" * 500}).status_code == 422
    bad = {"user": "u1", "pr": "not-a-pr", "person": "bob", "verdict": "reject"}
    assert c.post("/api/feedback", json=bad).status_code == 422
    assert c.post("/api/feedback", json={**bad, "pr": "o/r#1", "person": "bob; DROP"}).status_code == 422
    assert c.get("/api/memory", params={"user": "../x"}).status_code == 422
    assert c.post("/api/coord/decide", json={"task": "bad task"}).status_code == 422


def test_unknown_tenant_is_404(monkeypatch):
    monkeypatch.setattr(api, "budget_ok", lambda: True)
    assert c.post("/api/ask", json={"question": "who knows x", "tenant": "nope"}).status_code == 404


def test_rate_limit_is_per_forwarded_visitor(monkeypatch):
    monkeypatch.setattr(api, "budget_ok", lambda: True)
    api.HITS.clear()
    h = {"x-forwarded-for": "203.0.113.7, 10.0.0.1"}
    codes = [c.post("/api/ask", json={"question": "who knows x", "tenant": "nope"}, headers=h).status_code for _ in range(api.LIMIT + 2)]
    assert codes[: api.LIMIT] == [404] * api.LIMIT and codes[api.LIMIT:] == [429, 429]
    other = c.post("/api/ask", json={"question": "who knows x", "tenant": "nope"}, headers={"x-forwarded-for": "198.51.100.9"})
    assert other.status_code == 404  # a different visitor is unaffected
    api.HITS.clear()


def test_daily_budget_stops_llm_calls(monkeypatch):
    monkeypatch.setattr(api, "budget_ok", lambda: False)
    api.HITS.clear()
    assert c.post("/api/ask", json={"question": "who knows x"}).status_code == 429
    api.HITS.clear()
