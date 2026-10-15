"""HTTP API + static UI. Public demo: per-IP rate limit protects the OpenAI budget."""
import json, queue, threading, time
from collections import defaultdict, deque
from pathlib import Path
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from . import coord, mem, tools
from .agent import ask
from .config import env
from .db import db, kb, ro, graph_name

ROOT = Path(__file__).resolve().parent.parent
app = FastAPI(title="Keystone")
HITS: dict[str, deque] = defaultdict(deque)          # LLM questions
CHEAP: dict[str, deque] = defaultdict(deque)         # reads/writes that cost no LLM call
LIMIT, CHEAP_LIMIT, WINDOW = 25, 150, 3600


def client_ip(request: Request) -> str:
    """Behind Vercel the socket peer is the proxy; the visitor is the first X-Forwarded-For hop."""
    xff = request.headers.get("x-forwarded-for", "")
    return xff.split(",")[0].strip() or (request.client.host if request.client else "?")


def limited(ip: str, store=None, limit: int | None = None) -> bool:
    q, now = (HITS if store is None else store)[ip], time.time()
    while q and now - q[0] > WINDOW:
        q.popleft()
    if len(q) >= (LIMIT if limit is None else limit):
        return True
    q.append(now)
    return False


def budget_ok() -> bool:
    """Global daily cap on LLM calls, kept in FalkorDB so it holds across serverless instances (protects the OpenAI budget)."""
    n = db().select_graph("ops_meta").query("MERGE (m:Meter {day:$d}) SET m.n = coalesce(m.n, 0) + 1 RETURN m.n",
                                            {"d": time.strftime("%Y-%m-%d")}).result_set[0][0]
    return n <= int(env("DAILY_ASK_CAP", "400"))


class Turn(BaseModel):
    q: str = Field(max_length=400)
    a: str = Field(max_length=1200)


class Ask(BaseModel):
    tenant: str = "falkordb"
    question: str = Field(min_length=3, max_length=400)
    user: str = Field(default="demo", pattern=r"^[A-Za-z0-9_-]{1,40}$")
    history: list[Turn] = Field(default_factory=list, max_length=3)  # working memory: the last few turns of this chat


class Coord(BaseModel):
    tenant: str = "falkordb"
    worker: str = Field(default="router-1", pattern=r"^[A-Za-z0-9_-]{1,30}$")
    task: str = Field(default="", pattern=r"^([A-Za-z0-9_.-]{1,60}/[A-Za-z0-9_.-]{1,100}#\d{1,7})?$")
    approve: bool = False
    user: str = Field(default="demo", pattern=r"^[A-Za-z0-9_-]{1,40}$")


class DemoReviewers(BaseModel):
    tenant: str = "falkordb"
    user: str = Field(pattern=r"^[A-Za-z0-9_-]{1,40}$")
    pr: str = Field(pattern=r"^[A-Za-z0-9_.-]{1,60}/[A-Za-z0-9_.-]{1,100}#\d{1,7}$")


class DemoLeave(BaseModel):
    tenant: str = "falkordb"
    user: str = Field(pattern=r"^[A-Za-z0-9_-]{1,40}$")
    person: str = Field(pattern=r"^[A-Za-z0-9-]{1,39}$")
    days: int = Field(default=14, ge=1, le=60)
    reason: str = Field(default="on leave", max_length=100)


class Feedback(BaseModel):
    user: str = Field(pattern=r"^[A-Za-z0-9_-]{1,40}$")
    pr: str = Field(pattern=r"^[A-Za-z0-9_.-]{1,60}/[A-Za-z0-9_.-]{1,100}#\d{1,7}$")
    person: str = Field(pattern=r"^[A-Za-z0-9-]{1,39}$")
    verdict: str
    reason: str = Field(default="", max_length=200)
    scope: str = Field(default="*", max_length=160)


@app.get("/api/tenants")
def tenants():
    return [g[3:] for g in db().list_graphs() if g.startswith("kb_")]


def ask_checks(body: Ask, request: Request):
    if limited(client_ip(request)):
        raise HTTPException(429, "demo rate limit reached, try again later")
    if not budget_ok():
        raise HTTPException(429, "daily demo budget reached, please come back tomorrow")
    known_tenant(body.tenant)


def turns_of(body: Ask):
    return [m for t in body.history for m in ({"role": "user", "content": t.q}, {"role": "assistant", "content": t.a})]


@app.post("/api/ask")
def api_ask(body: Ask, request: Request):
    ask_checks(body, request)
    return ask(body.tenant, body.question, body.user, turns_of(body))


@app.post("/api/ask/stream")
def api_ask_stream(body: Ask, request: Request):
    """Same answer as /api/ask, streamed as one JSON event per line so the UI can show the agent's real steps."""
    ask_checks(body, request)
    q: queue.Queue = queue.Queue()

    def work():
        try:
            q.put({"e": "final", "result": ask(body.tenant, body.question, body.user, turns_of(body), on_event=q.put)})
        except Exception as ex:  # surface to the client instead of a dropped stream
            q.put({"e": "error", "message": f"{type(ex).__name__}: {str(ex)[:160]}"})
        q.put(None)

    threading.Thread(target=work, daemon=True).start()

    def gen():
        while (item := q.get()) is not None:
            yield json.dumps(item, ensure_ascii=False) + "\n"

    return StreamingResponse(gen(), media_type="application/x-ndjson", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/api/feedback")
def feedback(body: Feedback):
    try:
        mem.give_feedback(body.user, body.pr, body.person, body.verdict, body.reason, body.scope)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True}


def guard(request: Request):
    if limited(client_ip(request), CHEAP, CHEAP_LIMIT):
        raise HTTPException(429, "demo rate limit reached, try again later")


def known_tenant(t: str):
    if graph_name("kb", t) not in db().list_graphs():
        raise HTTPException(404, "unknown tenant")


@app.post("/api/demo/reviewers")
def d_reviewers(b: DemoReviewers, request: Request):
    guard(request); known_tenant(b.tenant)
    return tools.suggest_reviewers(b.tenant, b.pr, n=4, user=b.user)["data"]


@app.post("/api/demo/unavailable")
def d_unavailable(b: DemoLeave, request: Request):
    guard(request); known_tenant(b.tenant)
    return tools.remember_unavailable(b.tenant, b.person, b.days, b.reason, user=b.user)["data"]


@app.post("/api/demo/forget")
def d_forget(b: DemoLeave, request: Request):
    guard(request); known_tenant(b.tenant)
    return tools.forget_unavailable(b.tenant, b.person, user=b.user)["data"]


@app.post("/api/coord/triage")
def c_triage(b: Coord, request: Request):
    guard(request)
    return {"queued": coord.triage(b.tenant)}


@app.post("/api/coord/route")
def c_route(b: Coord, request: Request):
    guard(request)
    tid = coord.claim(b.tenant, b.worker)
    return {"task": tid, "proposal": coord.propose(b.tenant, tid, b.worker, b.user) if tid else None}


@app.post("/api/coord/decide")
def c_decide(b: Coord, request: Request):
    guard(request)
    return coord.decide(b.tenant, b.task, b.approve, b.user)


@app.get("/api/coord/board")
def c_board(tenant: str = "falkordb"):
    return coord.board(tenant)


@app.get("/api/memory")
def memory(user: str = Query(pattern=r"^[A-Za-z0-9_-]{1,40}$")):
    return mem.summary(user)


@app.get("/api/overview")
def overview(tenant: str = "falkordb"):
    g = kb(tenant)
    stats = {l: ro(g, f"MATCH (n:{l}) RETURN count(n)")[0][0] for l in ("Person", "PR", "Issue", "Module", "Decision", "Repo")}
    people = ro(g, "MATCH (p:Person) WHERE p.pagerank IS NOT NULL RETURN p.login, p.home, p.pagerank, p.acts ORDER BY p.acts DESC LIMIT 200")
    keep = {p[0] for p in people}
    links = [r for r in ro(g, "MATCH (a:Person)-[c:COLLAB]->(b:Person) WHERE c.n >= 1 RETURN a.login, b.login, c.n") if r[0] in keep and r[1] in keep]
    linked = {x for r in links for x in r[:2]}  # isolated contributors would only be dots in rows: show the connected network
    nodes = [p for p in people if p[0] in linked][:90]
    ids = {p[0] for p in nodes}
    return {"stats": stats, "nodes": [{"id": a, "community": b, "pagerank": c, "acts": d} for a, b, c, d in nodes],
            "edges": [{"source": a, "target": b, "n": n} for a, b, n in links if a in ids and b in ids]}


@app.get("/api/expand")
def expand(request: Request, tenant: str = "falkordb", kind: str = Query(pattern=r"^(Person|PR|Issue|Module|Decision)$"),
           id: str = Query(pattern=r"^[A-Za-z0-9_.:/#@-]{1,200}$")):
    """Neighbours of one node for the interactive graphs (read-only, capped)."""
    guard(request); known_tenant(tenant)
    return tools.expand(tenant, kind, id)


@app.get("/api/ticker")
def ticker(tenant: str = "falkordb"):
    """Latest verified decisions, for the live strip under the hero."""
    rows = ro(kb(tenant), "MATCH (d:Decision)-[:DECIDED_IN]->(s) RETURN d.text, s.id, d.ts ORDER BY d.ts DESC LIMIT 16")
    return [{"text": t, "source": sid, "date": time.strftime("%Y-%m-%d", time.gmtime(ts))} for t, sid, ts in rows]


@app.get("/api/risk")
def risk(tenant: str = "falkordb", repo: str | None = None):
    return {"bus_factor": tools.bus_factor(tenant, repo)["data"], "bridges": tools.bridges(tenant)["data"]}


@app.get("/api/riskmap")
def riskmap(tenant: str = "falkordb"):
    return tools.risk_map(tenant)


@app.get("/api/eval")
def evaluation():
    out = {}
    for name, key in (("eval_result.json", None), ("qa_eval.json", "qa"), ("facts.json", "facts")):
        f = ROOT / "data" / name
        if f.exists():
            d = json.loads(f.read_text())
            out.update(d if key is None else {key: ({k: {m: v for m, v in r.items() if m != "rows"} for k, r in d.items()} if key == "qa" else d)})
    return out


app.mount("/", StaticFiles(directory=ROOT / "public", html=True), name="web")
