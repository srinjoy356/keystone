"""Two-agent handoff through shared graph state (graph ops_<tenant>).
Triage agent enqueues Task nodes for open PRs; Router workers claim them; a human approves; an executor acts.
Claiming is ONE write query, and FalkorDB serialises writes, so N racing workers cannot claim the same task."""
import json, os, time
import httpx
from . import tools
from .db import db, graph_name, ro

STATUS = ("queued", "claimed", "proposed", "approved", "rejected", "done")


def og(tenant: str):
    g = db().select_graph(graph_name("ops", tenant))
    if tenant not in _ready:
        try:
            g.query("CREATE INDEX FOR (t:Task) ON (t.id)")
        except Exception as e:  # index survives restarts
            if "already indexed" not in str(e).lower():
                raise
        _ready.add(tenant)
    return g


_ready: set[str] = set()


def triage(tenant: str, limit: int = 20) -> int:
    """Agent 1: find open PRs in the knowledge graph and queue them with a risk note (do their files sit in at-risk modules?)."""
    kbg = db().select_graph(graph_name("kb", tenant))
    prs = ro(kbg, """MATCH (pr:PR {state:'OPEN'}) OPTIONAL MATCH (pr)-[:TOUCHES]->(f:File)
                     RETURN pr.id, pr.title, pr.createdAt, count(f) AS files ORDER BY pr.createdAt DESC LIMIT $n""", {"n": limit})
    risky = {r["module"] for r in tools.bus_factor(tenant, limit=40)["data"]["at_risk_modules"]}
    g, n = og(tenant), 0
    for pid, title, created, files in prs:
        mods = {r[0] for r in ro(kbg, "MATCH (:PR {id:$id})-[:TOUCHES]->(:File)-[:IN]->(m:Module) RETURN DISTINCT m.id", {"id": pid})}
        hit = sorted(mods & risky)
        g.query("""MERGE (t:Task {id:$id}) ON CREATE SET t.status='queued', t.created=$now
                   SET t.title=$title, t.files=$files, t.risk=$risk, t.prio=$prio""",
                {"id": pid, "title": title, "files": files, "now": int(time.time()), "risk": json.dumps(hit), "prio": len(hit) * 10 + min(files, 50)})
        n += 1
    return n


def claim(tenant: str, worker: str):
    """Agent 2 claims the highest-priority queued task. Single atomic write."""
    rows = og(tenant).query("""MATCH (t:Task {status:'queued'}) WITH t ORDER BY t.prio DESC, t.id LIMIT 1
                               SET t.status='claimed', t.by=$w, t.claimedAt=$now RETURN t.id""",
                            {"w": worker, "now": int(time.time())}).result_set
    return rows[0][0] if rows else None


def propose(tenant: str, task_id: str, worker: str, user: str | None = None):
    res = tools.suggest_reviewers(tenant, task_id, user)["data"]
    og(tenant).query("MATCH (t:Task {id:$id, by:$w, status:'claimed'}) SET t.status='proposed', t.proposal=$p",
                     {"id": task_id, "w": worker, "p": json.dumps(res)})
    return res


def decide(tenant: str, task_id: str, approve: bool, who: str):
    g = og(tenant)
    rows = g.query("""MATCH (t:Task {id:$id, status:'proposed'}) SET t.status=$s, t.decidedBy=$who, t.decidedAt=$now RETURN t.proposal""",
                   {"id": task_id, "s": "approved" if approve else "rejected", "who": who, "now": int(time.time())}).result_set
    if not rows:
        return {"error": "task is not awaiting a decision"}
    return execute(tenant, task_id, json.loads(rows[0][0])) if approve else {"status": "rejected"}


def execute(tenant: str, task_id: str, proposal: dict):
    """Request the suggested reviewers. Real write only if a write token is set AND the repo is allowlisted; otherwise dry run."""
    repo, num = task_id.split("#")
    reviewers = [s["person"] for s in proposal.get("suggestions", [])][:2]
    allow = {r.strip() for r in os.environ.get("KEYSTONE_WRITE_REPOS", "").split(",") if r.strip()}
    token, live = os.environ.get("GITHUB_WRITE_TOKEN"), False
    payload = {"method": "POST", "url": f"https://api.github.com/repos/{repo}/pulls/{num}/requested_reviewers", "json": {"reviewers": reviewers}}
    status = "dry_run"
    if token and repo in allow:
        r = httpx.post(payload["url"], json=payload["json"], headers={"Authorization": f"Bearer {token}"}, timeout=20)
        status, live = ("executed" if r.status_code < 300 else f"failed_{r.status_code}"), True
    og(tenant).query("MATCH (t:Task {id:$id}) SET t.status='done', t.action=$a, t.actionStatus=$s",
                     {"id": task_id, "a": json.dumps(payload), "s": status})
    return {"status": status, "live": live, "request": payload}


def board(tenant: str):
    rows = ro(og(tenant), "MATCH (t:Task) RETURN t.id, t.title, t.status, t.by, t.risk, t.prio, t.actionStatus ORDER BY t.prio DESC LIMIT 50")
    return [{"id": a, "title": b, "status": c, "by": d, "risk": json.loads(e or "[]"), "prio": f, "action": g} for a, b, c, d, e, f, g in rows]
