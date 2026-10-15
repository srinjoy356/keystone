"""Concurrency check: many Router workers race for tasks; every task must be claimed exactly once."""
from concurrent.futures import ThreadPoolExecutor
from keystone import coord
from keystone.db import db, graph_name

T = "falkordb"


def test_claims_are_exclusive():
    db().select_graph(graph_name("ops", T)).query("MATCH (t:Task) DETACH DELETE t") if "ops_" + T in db().list_graphs() else None
    g = coord.og(T)
    for i in range(30):
        g.query("CREATE (:Task {id:$id, status:'queued', prio:$p})", {"id": f"x#{i}", "p": i})
    with ThreadPoolExecutor(12) as ex:
        got = [r for r in ex.map(lambda w: [coord.claim(T, f"w{w % 4}") for _ in range(6)], range(10)) for r in r]
    claimed = [x for x in got if x]
    assert len(claimed) == 30 and len(set(claimed)) == 30, (len(claimed), len(set(claimed)))
    g.query("MATCH (t:Task) DETACH DELETE t")
