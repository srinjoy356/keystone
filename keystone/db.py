"""FalkorDB access. One named graph per tenant (kb_<tenant>) and per user (mem_<user>)."""
import re, contextvars
from falkordb import FalkorDB
from .config import env
from .tracing import span

_db = None
QUERY_LOG: contextvars.ContextVar = contextvars.ContextVar("query_log", default=None)


def db() -> FalkorDB:
    global _db
    if _db is None:
        if env("FALKORDB_TARGET", "local") == "cloud":
            _db = FalkorDB(host=env("FALKORDB_HOST"), port=int(env("FALKORDB_PORT")),
                           username=env("FALKORDB_USERNAME"), password=env("FALKORDB_PASSWORD"))
        else:
            _db = FalkorDB(host="localhost", port=6379)
    return _db


def graph_name(prefix: str, ident: str) -> str:
    """Tenant isolation is structural: a different graph per tenant/user, never a property filter."""
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", ident):
        raise ValueError("bad tenant id")
    return f"{prefix}_{ident}"


def kb(tenant: str = "falkordb"):
    return db().select_graph(graph_name("kb", tenant))


def ro(graph, cypher: str, params: dict | None = None, timeout_ms: int = 5000):
    """Read-only, parameterised, time-limited. GRAPH.RO_QUERY makes the server reject any write."""
    log = QUERY_LOG.get()
    with span("falkordb.query", **{"db.system": "falkordb", "db.operation": "GRAPH.RO_QUERY", "db.query.text": " ".join(cypher.split())[:200]}) as sp:
        res = graph.ro_query(cypher, params or {}, timeout=timeout_ms)
        if sp:
            sp.set_attribute("db.rows", len(res.result_set))
            sp.set_attribute("db.run_time_ms", res.run_time_ms)
    if log is not None:
        log.append({"cypher": " ".join(cypher.split()), "rows": len(res.result_set), "ms": res.run_time_ms})
    return res.result_set
