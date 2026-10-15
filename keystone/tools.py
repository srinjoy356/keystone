"""Agent tools. Each is fixed, parameterised, read-only Cypher over the tenant graph and returns
{data, evidence:{nodes,edges}, cypher}. The LLM never writes Cypher and never touches the database."""
import json, math, time
from functools import lru_cache
from pathlib import Path
from .db import kb, ro
from .load_decisions import embed
from . import mem
from .load import modules_of
from .queries import signals, repo_signal, DAY

EVAL = Path(__file__).resolve().parent.parent / "data" / "eval_result.json"
DEFAULT_W = ({"file": 1, "module": 1, "social": 0.5, "repo": 0.5}, 365)


def blend_cfg():
    if EVAL.exists():
        b = json.loads(EVAL.read_text())["best"]
        return b["w"], b["tau"]
    return DEFAULT_W


def _ev():
    return {"nodes": {}, "edges": []}


def _n(ev, id, label, name=None, **kw):
    ev["nodes"].setdefault(id, {"id": id, "label": label, "name": name or id, **kw})


def _out(data, ev, cypher):
    return {"data": data, "evidence": {"nodes": list(ev["nodes"].values()), "edges": ev["edges"]}, "cypher": cypher}


def resolve_module(g, text: str):
    rows = ro(g, """MATCH (m:Module) WHERE toLower(m.id) CONTAINS toLower($t) AND m.path <> '/'
                    OPTIONAL MATCH (m)<-[:IN]-(f:File)<-[:TOUCHES]-(pr:PR) WITH m, count(DISTINCT pr) AS n
                    RETURN m.id, n ORDER BY n DESC LIMIT 5""", {"t": text})
    if rows:
        return rows
    return ro(g, """MATCH (f:File)-[:IN]->(m:Module) WHERE toLower(f.path) CONTAINS toLower($t)
                    RETURN m.id, count(f) AS n ORDER BY n DESC LIMIT 5""", {"t": text})


TOPIC = """CALL db.idx.vector.queryNodes('PR','emb',40,vecf32($v)) YIELD node, score
MATCH (p:Person)-[r:AUTHORED|REVIEWED]->(node)
RETURN p.login, sum((1.0 - score) * (CASE type(r) WHEN 'REVIEWED' THEN 1.0 ELSE 0.6 END) * exp(-($now - node.createdAt) / $tau)) AS s,
       count(DISTINCT node) AS prs, max(node.createdAt) AS last, p.community"""
TOPIC_PRS = """CALL db.idx.vector.queryNodes('PR','emb',6,vecf32($v)) YIELD node, score
RETURN node.id, node.title, score ORDER BY score"""


def who_knows(tenant: str, target: str):
    """Path-like target -> module hierarchy walk. Free-text topic -> vector recall over PRs, then graph expansion to people."""
    g, ev, now = kb(tenant), _ev(), int(time.time())
    target = target.strip()
    mods = resolve_module(g, target) if " " not in target else []
    if not mods:
        v = embed([target])[0]
        rows = ro(g, TOPIC, {"v": v, "now": now, "tau": 540 * DAY})
        rows = sorted(rows, key=lambda r: -r[1])[:5]
        if not rows:
            return _out({"error": f"nothing in the graph relates to '{target}'"}, ev, "WHO_KNOWS_TOPIC")
        tot = sum(r[1] for r in rows) or 1
        prs = ro(g, TOPIC_PRS, {"v": v})
        _n(ev, "topic:" + target[:40], "Topic", target[:40])
        for pid, title, dist in prs:
            _n(ev, pid, "PR", pid, title=title)
            ev["edges"].append({"source": pid, "target": "topic:" + target[:40], "type": "ABOUT"})
        out = []
        for login, s, n, last, comm in rows:
            _n(ev, login, "Person", login, community=comm)
            out.append({"person": login, "share": round(s / tot, 2), "related_prs": n, "last_active_days": (now - last) // DAY})
        for u, pid in ro(g, "MATCH (p:Person)-[:AUTHORED|REVIEWED]->(pr:PR) WHERE p.login IN $us AND pr.id IN $ps RETURN DISTINCT p.login, pr.id",
                         {"us": [o["person"] for o in out], "ps": [x[0] for x in prs]}):
            ev["edges"].append({"source": u, "target": pid, "type": "WORKED_ON"})
        return _out({"topic": target, "route": "vector recall over PRs, then graph expansion to authors and reviewers",
                     "closest_prs": [{"pr": a, "title": b} for a, b, _ in prs], "experts": out}, ev, "WHO_KNOWS_TOPIC")
    mid = mods[0][0]
    rows = ro(g, """MATCH (m:Module {id:$mid})<-[:PARENT*0..3]-(:Module)<-[:IN]-(:File)<-[:TOUCHES]-(pr:PR)<-[r:AUTHORED|REVIEWED]-(p:Person)
                    RETURN p.login, sum((CASE type(r) WHEN 'REVIEWED' THEN 1.0 ELSE 0.5 END) * exp(-($now - pr.createdAt) / $tau)) AS s,
                           count(DISTINCT pr) AS prs, max(pr.createdAt) AS last, p.community
                    ORDER BY s DESC LIMIT 5""", {"mid": mid, "now": now, "tau": 180 * DAY})
    tot = sum(r[1] for r in rows) or 1
    _n(ev, mid, "Module", mid)
    out = []
    for login, s, prs, last, comm in rows:
        _n(ev, login, "Person", login, community=comm)
        ev["edges"].append({"source": login, "target": mid, "type": "KNOWS", "w": round(s, 2)})
        out.append({"person": login, "share": round(s / tot, 2), "prs": prs, "last_active_days": (now - last) // DAY})
    return _out({"module": mid, "alternatives": [m[0] for m in mods[1:]], "experts": out}, ev, "WHO_KNOWS")


def _pr(g, ref: str):
    rows = ro(g, "MATCH (pr:PR) WHERE pr.id = $r OR pr.id ENDS WITH $s RETURN pr.id, pr.createdAt, pr.state, pr.title LIMIT 3",
              {"r": ref, "s": "#" + ref.lstrip("#").split("#")[-1]})
    return rows[0] if rows else None


def suggest_reviewers(tenant: str, pr: str, user: str | None = None):
    g, ev = kb(tenant), _ev()
    row = _pr(g, pr)
    if not row:
        return _out({"error": f"PR '{pr}' not found"}, ev, "SUGGEST_REVIEWERS")
    pid, created, state, title = row
    author = ro(g, "MATCH (p:Person)-[:AUTHORED]->(:PR {id:$id}) RETURN p.login", {"id": pid})
    author = author[0][0] if author else ""
    files = [r[0] for r in ro(g, "MATCH (:PR {id:$id})-[:TOUCHES]->(f:File) RETURN f.id", {"id": pid})]
    asof = int(time.time()) if state == "OPEN" else created
    w, tau = blend_cfg()
    sig = signals(g, files, author, asof, tau, need=[k for k, v in w.items() if v > 0 and k != "repo"])  # skip zero-weight signals
    sig["repo"] = repo_signal(g, pid.split("#")[0], author, asof, tau) if w.get("repo", 0) > 0 else {}
    tot: dict[str, float] = {}
    for name, wt in w.items():
        d = sig.get(name, {})
        mx = max(d.values(), default=0) or 1
        for u, v in d.items():
            tot[u] = tot.get(u, 0) + wt * v / mx
    notes = []
    chains = [modules_of(pid.split("#")[0], f.split(":", 1)[1]) for f in files]
    mods = [x for c in chains for x in c]
    lvl1 = [c[0] for c in chains]  # top-level directory of each file: the scope a learned rule applies to
    if user:
        tot, notes = mem.adjust(user, tot, mods)
    top = sorted(tot, key=lambda u: (-tot[u], u))[:3]
    top = [u for u in top if tot[u] >= 0.15 * tot[top[0]]]  # drop weak candidates rather than list them
    _n(ev, pid, "PR", pid, title=title)
    out = []
    for u in top:
        why = ro(g, """MATCH (p:Person {login:$u})-[r:AUTHORED|REVIEWED]->(pr:PR)-[:TOUCHES]->(f:File) WHERE f.id IN $files AND pr.createdAt < $asof
                       WITH pr, type(r) AS role, count(f) AS shared RETURN pr.id, pr.title, role, shared ORDER BY shared DESC, pr.createdAt DESC LIMIT 2""",
                 {"u": u, "files": files, "asof": asof})
        _n(ev, u, "Person", u)
        ev["edges"].append({"source": u, "target": pid, "type": "SUGGESTED", "w": round(tot[u], 2)})
        for wid, wt_, role, shared in why:
            _n(ev, wid, "PR", wid, title=wt_)
            ev["edges"].append({"source": u, "target": wid, "type": role})
        out.append({"person": u, "score": round(tot[u], 2),
                    "signals": {k: round(sig[k].get(u, 0) / (max(sig[k].values(), default=0) or 1), 2) for k in w if sig.get(k)},
                    "because": [{"pr": a, "title": b, "role": c, "shared_files": d} for a, b, c, d in why]})
    return _out({"pr": pid, "title": title, "author": author, "asof_days_ago": (int(time.time()) - asof) // DAY,
                 "files": len(files), "suggestions": out, "memory_notes": notes,
                 "scope": max(set(lvl1), key=lvl1.count, default="*")}, ev, "SUGGEST_REVIEWERS")


def bus_factor(tenant: str, repo: str | None = None, limit: int = 6):
    return _bus_factor(tenant, repo, limit, int(time.time() // 300))  # 5-minute cache: history changes slowly, the scan is the heaviest read


@lru_cache(maxsize=64)
def _bus_factor(tenant: str, repo: str | None, limit: int, _bucket: int):
    g, ev, now = kb(tenant), _ev(), int(time.time())
    rows = ro(g, """MATCH (m:Module)<-[:IN]-(:File)<-[:TOUCHES]-(pr:PR)<-[:AUTHORED|REVIEWED]-(p:Person)
                    WHERE pr.createdAt > $since AND ($repo IS NULL OR m.repo = $repo)
                    RETURN m.id, p.login, count(DISTINCT pr) AS n, max(pr.createdAt) AS last""",
              {"since": now - 365 * DAY, "repo": repo}, timeout_ms=15000)
    mods: dict[str, list] = {}
    for m, p, n, last in rows:
        mods.setdefault(m, []).append((p, n, last))
    risk = []
    for m, ps in mods.items():
        ps.sort(key=lambda x: -x[1])
        total = sum(n for _, n, _ in ps)
        if total < 10 or m.endswith(':/') or ':.github' in m:  # skip repo-root and CI plumbing
            continue
        top = ps[0]
        backups = [p for p, n, last in ps[1:] if n / total >= 0.15 and now - last < 120 * DAY]
        share = top[1] / total
        if share < 0.4:  # only genuine concentration counts as risk
            continue
        risk.append({"module": m, "top_expert": top[0], "share": round(share, 2), "active_backups": len(backups),
                     "recent_prs": total, "top_expert_last_active_days": (now - top[2]) // DAY,
                     "score": share * math.log(1 + total) * (1.5 if not backups else 1)})
    picked, per_repo = [], {}
    for r in sorted(risk, key=lambda r: -r["score"]):  # at most 2 per repo so one busy repo cannot fill the list
        repo_name = r["module"].split(":", 1)[0]
        if per_repo.get(repo_name, 0) < 2:
            picked.append(r); per_repo[repo_name] = per_repo.get(repo_name, 0) + 1
    risk = picked[:limit]
    for r in risk:
        _n(ev, r["module"], "Module", r["module"], risk=round(r["score"], 2))
        _n(ev, r["top_expert"], "Person", r["top_expert"])
        ev["edges"].append({"source": r["top_expert"], "target": r["module"], "type": "KNOWS", "w": r["share"]})
        r.pop("score")
    return _out({"at_risk_modules": risk, "note": "module-level knowledge concentration, not a judgment of any individual"}, ev, "BUS_FACTOR")


def bridges(tenant: str, limit: int = 5):
    g, ev = kb(tenant), _ev()
    rows = ro(g, """MATCH (p:Person) WHERE p.bridge IS NOT NULL AND p.bridge > 0
                    OPTIONAL MATCH (p)-[:COLLAB]-(q:Person)
                    RETURN p.login, p.bridge, p.pagerank, p.community, count(DISTINCT q.community) AS reach ORDER BY p.bridge DESC LIMIT $n""", {"n": limit})
    out = []
    for login, br, pr_, comm, reach in rows:
        _n(ev, login, "Person", login, community=comm)
        out.append({"person": login, "bridge_score": round(br, 1), "pagerank": round(pr_, 4), "community": comm, "communities_reached": reach})
    return _out({"bridge_people": out, "meaning": "betweenness on the author->reviewer graph: people who connect otherwise separate groups"}, ev, "BRIDGES")


def connection(tenant: str, a: str, b: str):
    g, ev = kb(tenant), _ev()
    rows = ro(g, """MATCH (a:Person {login:$a}), (b:Person {login:$b})
                    WITH shortestPath((a)-[:KNOWS|KNOWN_BY|LINKS*..6]->(b)) AS p
                    RETURN [n IN nodes(p) | coalesce(n.login, n.id)], [n IN nodes(p) | labels(n)[0]], [r IN relationships(p) | type(r)]""",
              {"a": a, "b": b}, timeout_ms=8000)
    if not rows:
        return _out({"error": "no path"}, ev, "CONNECTION")
    names, labels, types = rows[0]
    for nm, lb in zip(names, labels):
        _n(ev, nm, lb, nm)
    for i, t in enumerate(types):
        ev["edges"].append({"source": names[i], "target": names[i + 1], "type": t})
    return _out({"hops": len(types), "path": [f"{n} ({l})" for n, l in zip(names, labels)]}, ev, "CONNECTION")


WHY = """CALL db.idx.vector.queryNodes('Decision','emb',$k,vecf32($v)) YIELD node, score
MATCH (node)-[:DECIDED_IN]->(pr) OPTIONAL MATCH (p:Person)-[:STATED]->(node)
RETURN node.id, node.text, node.why, node.quote, node.ts, pr.id, pr.title, pr.url, p.login, labels(pr)[0], score ORDER BY score"""


# Dated neighbours: other decisions that touched the same module and are semantically close (graph constraint + vector distance).
RELATED = """MATCH (d:Decision {id:$id})-[:DECIDED_IN]->(:PR)-[:TOUCHES]->(:File)-[:IN]->(m:Module) WHERE m.path <> '/'
WITH d, collect(DISTINCT m.id) AS ms
CALL db.idx.vector.queryNodes('Decision','emb',10,d.emb) YIELD node, score
WITH d, ms, node, score WHERE node.id <> d.id AND score < 0.5
MATCH (node)-[:DECIDED_IN]->(s:PR)-[:TOUCHES]->(:File)-[:IN]->(m2:Module) WHERE m2.id IN ms
RETURN DISTINCT node.id, node.text, node.ts, s.id, score ORDER BY node.ts"""


def why_decision(tenant: str, question: str, k: int = 5):
    """Vector search over verified decisions, then one graph hop to the source thread and the person who said it.
    (Tried title-augmented embeddings and rank-fusion with PR-title search: both scored lower on MRR, see README.)"""
    g, ev = kb(tenant), _ev()
    out = []
    for did, text, why, quote, ts, pid, ptitle, url, who, kind, score in ro(g, WHY, {"k": k, "v": embed([question])[0]}):
        _n(ev, did, "Decision", text[:60]); _n(ev, pid, kind, pid, title=ptitle)
        ev["edges"].append({"source": did, "target": pid, "type": "DECIDED_IN"})
        if who:
            _n(ev, who, "Person", who); ev["edges"].append({"source": who, "target": did, "type": "STATED"})
        rel = ro(g, RELATED, {"id": did}) if len(out) < 3 else []  # timeline context for the top results only
        fmt = lambda r: {"date": time.strftime("%Y-%m-%d", time.gmtime(r[2])), "decision": r[1], "source": r[3]}
        out.append({"decision": text, "rationale": why, "verbatim_quote": quote, "stated_by": who, "pr": pid, "pr_title": ptitle,
                    "source_kind": kind, "url": url, "date": time.strftime("%Y-%m-%d", time.gmtime(ts)), "distance": round(score, 2),
                    "earlier_related": [fmt(r) for r in rel if r[2] < ts][-2:], "later_related": [fmt(r) for r in rel if r[2] > ts][:2]})
    return _out({"decisions": out, "note": "related = same module and semantically close; chronology only, not a claim that one replaced another"}, ev, "WHY_DECISION")


def recall_memory(tenant: str, topic: str, user: str | None = None):
    ev = _ev()
    return _out(mem.recall(user, topic) if user else {"note": "no user memory in this session"}, ev, "RECALL_MEMORY")


def remember_unavailable(tenant: str, person: str, days: int, reason: str = "", user: str | None = None):
    """Write to THIS USER's memory graph only: skip `person` in this user's reviewer suggestions for `days` days."""
    ev = _ev()
    if not user:
        return _out({"error": "no user session, nothing remembered"}, ev, "REMEMBER")
    if not ro(kb(tenant), "MATCH (p:Person {login:$p}) RETURN p.login", {"p": person}):
        return _out({"error": f"'{person}' is not a known contributor in this graph, nothing remembered"}, ev, "REMEMBER")
    days = max(1, min(int(days), 180))
    mem.add_rule(user, person, "*", days, reason)
    _n(ev, person, "Person", person)
    return _out({"remembered": f"will skip {person} in your reviewer suggestions for {days} days", "reason": reason}, ev, "REMEMBER")


def forget_unavailable(tenant: str, person: str, user: str | None = None):
    ev = _ev()
    n = mem.drop_rules(user, person) if user else 0
    return _out({"forgot_rules": n, "person": person}, ev, "FORGET")


TOOLS = {"remember_unavailable": remember_unavailable, "forget_unavailable": forget_unavailable, "recall_memory": recall_memory, "who_knows": who_knows, "suggest_reviewers": suggest_reviewers, "bus_factor": bus_factor, "bridges": bridges,
         "connection": connection, "why_decision": why_decision}
