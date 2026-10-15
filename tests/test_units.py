from keystone.decisions import verify, norm
from keystone.load import modules_of, pr_rows, ts
from keystone.db import graph_name
import pytest


def test_modules_chain_and_root():
    assert modules_of("o/r", "src/a/b/c/d.py") == ["o/r:src", "o/r:src/a", "o/r:src/a/b"]  # capped at 3 levels
    assert modules_of("o/r", "README.md") == ["o/r:/"]


def _pr(author="alice", typ="User"):
    a = lambda l, t="User": {"login": l, "__typename": t}
    return {"number": 7, "title": "t", "url": "u", "state": "MERGED", "createdAt": "2025-01-01T00:00:00Z", "mergedAt": None,
            "changedFiles": 1, "additions": 1, "deletions": 0, "author": a(author, typ),
            "files": {"nodes": [{"path": "x/y.py", "additions": 1, "deletions": 0}]},
            "reviews": {"nodes": [{"author": a("bob"), "state": "APPROVED"}, {"author": a("dependabot", "Bot"), "state": "COMMENTED"},
                                  {"author": a("alice"), "state": "COMMENTED"}]},
            "comments": {"nodes": [{"author": a("carol")}, {"author": None}]}, "closingIssuesReferences": {"nodes": []}}


def test_bots_authors_and_ghosts_are_excluded():
    r = pr_rows("o/r", _pr())
    assert [v["u"] for v in r["reviews"]] == ["bob"]  # no bot, no self-review
    assert r["comments"] == ["carol"]  # deleted accounts dropped
    assert ts("2025-01-01T00:00:00Z") == 1735689600


def test_quote_must_be_verbatim_substring():
    ms = [{"id": "m1", "who": "bob", "text": "We reject this because it   mutates\nstored data and breaks replay."}]
    good = {"decision": "d", "quote": "because it mutates stored data and breaks replay", "msg": "m1"}
    fake = {"decision": "d", "quote": "because it is slow and expensive for users", "msg": "m1"}
    short = {"decision": "d", "quote": "breaks replay", "msg": "m1"}
    kept, rejected = verify([good, fake, short, {"decision": "d", "quote": good["quote"], "msg": "m9"}], ms)
    assert [k["who"] for k in kept] == ["bob"] and rejected == 3
    assert norm("A  B\n") == "a b"


def test_tenant_ids_cannot_escape_graph_namespace():
    assert graph_name("kb", "falkordb") == "kb_falkordb"
    for bad in ("a b", "../x", "a;b", "", "x" * 41):
        with pytest.raises(ValueError):
            graph_name("kb", bad)
