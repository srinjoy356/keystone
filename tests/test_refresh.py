"""Refresh correctness: an upsert updates state without duplicating, and the incremental fetch stops at the watermark."""
from keystone import github, load
from keystone.db import db, kb, ro

T = "reftest"


def _pr(state="OPEN", reviewers=("bob",)):
    a = lambda l, t="User": {"login": l, "__typename": t}
    return {"number": 7, "title": "t", "url": "u", "state": state, "createdAt": "2025-01-01T00:00:00Z", "mergedAt": None,
            "changedFiles": 1, "additions": 1, "deletions": 0, "author": a("alice"),
            "files": {"nodes": [{"path": "x/y.py", "additions": 1, "deletions": 0}]},
            "reviews": {"nodes": [{"author": a(r), "state": "APPROVED"} for r in reviewers]},
            "comments": {"nodes": []}, "closingIssuesReferences": {"nodes": []}}


def test_upsert_updates_state_and_adds_reviewer_without_duplicates():
    try:
        load.load_prs(T, "o/r", [_pr("OPEN", ("bob",))])
        load.load_prs(T, "o/r", [_pr("MERGED", ("bob", "carol"))])  # same PR later: merged, one more reviewer
        g = kb(T)
        assert ro(g, "MATCH (p:PR) RETURN count(p)")[0][0] == 1
        assert ro(g, "MATCH (p:PR {id:'o/r#7'}) RETURN p.state")[0][0] == "MERGED"
        assert sorted(r[0] for r in ro(g, "MATCH (u:Person)-[:REVIEWED]->(:PR) RETURN u.login")) == ["bob", "carol"]
        load.load_prs(T, "o/r", [_pr("MERGED", ("bob", "carol"))])  # idempotent
        assert ro(g, "MATCH ()-[r:REVIEWED]->() RETURN count(r)")[0][0] == 2
    finally:
        db().select_graph(f"kb_{T}").delete()


def test_fetch_updated_stops_at_the_watermark(monkeypatch):
    pages = [{"repository": {"pullRequests": {"pageInfo": {"hasNextPage": True, "endCursor": "c1"},
                                              "nodes": [{"number": 3, "updatedAt": "2026-10-17T10:00:00Z"}, {"number": 2, "updatedAt": "2026-10-16T10:00:00Z"}]}},
              "rateLimit": {"remaining": 4000, "resetAt": "2026-10-17T11:00:00Z"}},
             {"repository": {"pullRequests": {"pageInfo": {"hasNextPage": True, "endCursor": "c2"},
                                              "nodes": [{"number": 1, "updatedAt": "2026-10-10T10:00:00Z"}]}},
              "rateLimit": {"remaining": 3990, "resetAt": "2026-10-17T11:00:00Z"}}]
    calls = iter(pages)
    monkeypatch.setattr(github, "_post", lambda client, variables, query=None: next(calls))
    since = github._epoch("2026-10-15T00:00:00Z")
    got = github.fetch_updated("o/r", since, "pullRequests")
    assert [n["number"] for n in got] == [3, 2]  # #1 is older than the watermark: stop, do not page further
