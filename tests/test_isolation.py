"""Structural isolation: tenants and users live in separate graphs; the agent's read path cannot write."""
import pytest
from keystone import mem, tools
from keystone.db import db, kb, ro


def test_tenants_share_no_nodes():
    a = {r[0] for r in ro(kb("falkordb"), "MATCH (r:Repo) RETURN r.name")}
    b = {r[0] for r in ro(kb("pallets"), "MATCH (r:Repo) RETURN r.name")}
    assert a and b and not (a & b)


def test_tools_only_see_their_tenant():
    out = tools.who_knows("pallets", "src")  # a path-like target that exists in both ecosystems' naming
    assert all(not m.startswith("FalkorDB/") for m in ([out["data"].get("module", "")] + out["data"].get("alternatives", [])))
    risk = tools.bus_factor("pallets")["data"]["at_risk_modules"]
    assert all(r["module"].startswith("pallets/") for r in risk)


def test_read_path_rejects_writes():
    with pytest.raises(Exception):
        ro(kb("falkordb"), "CREATE (:Evil {x:1})")
    with pytest.raises(Exception):
        ro(kb("falkordb"), "MATCH (p:Person) DETACH DELETE p")
    assert not ro(kb("falkordb"), "MATCH (e:Evil) RETURN e")


def test_user_memory_is_per_user_graph():
    mem.give_feedback("iso_a", "o/r#1", "someone", "reject", "test", "o/r:x")
    assert mem.summary("iso_a")["rules"]
    assert not mem.summary("iso_b")["rules"]
    for u in ("iso_a", "iso_b"):
        db().select_graph(f"mem_{u}").delete()
