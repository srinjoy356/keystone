"""Per-user agent memory, one FalkorDB graph per user (mem_<user>): structural isolation, no tenant filter to forget.
Episodic: past questions linked to the entities they touched.
Semantic: accept/reject feedback on people.
Procedural: learned AVOID rules (scoped to a module subtree, expiring) that change future reviewer suggestions."""
import hashlib, time
from .db import db, graph_name, ro

DAY = 86400


_ready: set[str] = set()


def mg(user: str):
    g = db().select_graph(graph_name("mem", user))
    if user not in _ready:  # RO_QUERY on a graph key that does not exist yet raises, so create it first
        g.query("MERGE (:User {id:$u})", {"u": user})
        _ready.add(user)
    return g


def record_episode(user: str, question: str, answer: str, tools: list[str], entity_ids: list[str]):
    ts = int(time.time())
    eid = hashlib.sha1(f"{user}{ts}{question}".encode()).hexdigest()[:10]
    mg(user).query("""MERGE (e:Episode {id:$id}) SET e.q=$q, e.a=$a, e.ts=$ts, e.tools=$tools
                      WITH e UNWIND $ents AS x MERGE (n:Entity {id:x}) MERGE (e)-[:ABOUT]->(n)""",
                   {"id": eid, "q": question[:300], "a": (answer or "")[:600], "ts": ts, "tools": tools, "ents": entity_ids[:12]})


def recall(user: str, topic: str, limit: int = 3):
    g = mg(user)
    eps = ro(g, """MATCH (e:Episode)-[:ABOUT]->(n:Entity) WHERE toLower(n.id) CONTAINS toLower($t) OR toLower(e.q) CONTAINS toLower($t)
                   RETURN DISTINCT e.q, e.a, e.ts ORDER BY e.ts DESC LIMIT $n""", {"t": topic, "n": limit})
    fb = ro(g, """MATCH (:User)-[f:FEEDBACK]->(p:Person) WHERE toLower(p.login) CONTAINS toLower($t) OR toLower(f.pr) CONTAINS toLower($t)
                  RETURN p.login, f.verdict, f.pr, f.reason, f.ts ORDER BY f.ts DESC LIMIT $n""", {"t": topic, "n": limit})
    return {"episodes": [{"q": q, "a": a[:200], "days_ago": (int(time.time()) - ts) // DAY} for q, a, ts in eps],
            "feedback": [{"person": p, "verdict": v, "pr": pr, "reason": r, "days_ago": (int(time.time()) - ts) // DAY} for p, v, pr, r, ts in fb]}


def give_feedback(user: str, pr: str, person: str, verdict: str, reason: str = "", scope: str = "*", days: int = 30):
    """reject -> also learn an AVOID rule for `scope` (a module id prefix) for `days` days."""
    if verdict not in ("accept", "reject"):
        raise ValueError("verdict must be accept or reject")
    now = int(time.time())
    g = mg(user)
    g.query("""MERGE (u:User {id:$u}) MERGE (p:Person {login:$p})
               CREATE (u)-[:FEEDBACK {verdict:$v, pr:$pr, reason:$r, ts:$ts}]->(p)""",
            {"u": user, "p": person, "v": verdict, "pr": pr, "r": reason[:200], "ts": now})
    if verdict == "reject":
        g.query("""MERGE (u:User {id:$u}) MERGE (p:Person {login:$p})
                   MERGE (u)-[a:AVOID {scope:$s}]->(p) SET a.until=$until, a.reason=$r, a.pr=$pr""",
                {"u": user, "p": person, "s": scope, "until": now + days * DAY, "r": reason[:200], "pr": pr})


def adjust(user: str, scores: dict[str, float], modules: list[str]):
    """Apply memory to reviewer scores. Returns (scores, explanations)."""
    now, notes, g = int(time.time()), [], mg(user)
    rules = ro(g, "MATCH (:User {id:$u})-[a:AVOID]->(p:Person) WHERE a.until > $now RETURN p.login, a.scope, a.reason, a.pr, a.until",
               {"u": user, "now": now})
    for login, scope, reason, pr, until in rules:
        if login in scores and (scope == "*" or any(m.startswith(scope) for m in modules)):
            scores.pop(login)
            notes.append(f"skipped {login}: you rejected them on {pr}" + (f" ({reason})" if reason else "") + f", rule expires in {(until - now) // DAY}d")
    accepted = dict(ro(g, "MATCH (:User {id:$u})-[f:FEEDBACK {verdict:'accept'}]->(p:Person) RETURN p.login, count(f)", {"u": user}))
    for login, n in accepted.items():
        if login in scores:
            scores[login] *= 1 + 0.1 * min(n, 3)
    return scores, notes


def summary(user: str):
    g, now = mg(user), int(time.time())
    rules = ro(g, "MATCH (:User)-[a:AVOID]->(p:Person) RETURN p.login, a.scope, a.reason, a.pr, a.until ORDER BY a.until DESC LIMIT 20")
    fb = ro(g, "MATCH (:User)-[f:FEEDBACK]->(p:Person) RETURN f.verdict, count(f)")
    eps = ro(g, "MATCH (e:Episode) RETURN e.q, e.ts, e.tools ORDER BY e.ts DESC LIMIT 8")
    return {"rules": [{"person": a, "scope": b, "reason": c, "pr": d, "expires_in_days": max(0, (e - now) // DAY)} for a, b, c, d, e in rules],
            "feedback": dict(fb), "episodes": [{"q": q, "days_ago": (now - t) // DAY, "tools": tl} for q, t, tl in eps]}


def add_rule(user: str, person: str, scope: str, days: int, reason: str):
    """Explicit 'avoid for N days' rule stated in conversation (procedural memory), scoped to a module prefix or '*'."""
    mg(user).query("""MERGE (u:User {id:$u}) MERGE (p:Person {login:$p})
                      MERGE (u)-[a:AVOID {scope:$s}]->(p) SET a.until=$until, a.reason=$r, a.pr='stated in chat'""",
                   {"u": user, "p": person, "s": scope, "until": int(time.time()) + days * DAY, "r": reason[:200]})


def drop_rules(user: str, person: str) -> int:
    g = mg(user)
    n = ro(g, "MATCH (:User {id:$u})-[a:AVOID]->(:Person {login:$p}) RETURN count(a)", {"u": user, "p": person})[0][0]
    g.query("MATCH (:User {id:$u})-[a:AVOID]->(:Person {login:$p}) DELETE a", {"u": user, "p": person})
    return n
