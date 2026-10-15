"""HTTP API + static UI. Public demo: per-IP rate limit protects the OpenAI budget."""
import json, time
from collections import defaultdict, deque
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from . import tools
from .agent import ask
from .db import db, kb, ro, graph_name

ROOT = Path(__file__).resolve().parent.parent
app = FastAPI(title="Keystone")
HITS: dict[str, deque] = defaultdict(deque)
LIMIT, WINDOW = 25, 3600


def limited(ip: str) -> bool:
    q, now = HITS[ip], time.time()
    while q and now - q[0] > WINDOW:
        q.popleft()
    if len(q) >= LIMIT:
        return True
    q.append(now)
    return False


class Ask(BaseModel):
    tenant: str = "falkordb"
    question: str = Field(min_length=3, max_length=400)


@app.get("/api/tenants")
def tenants():
    return [g[3:] for g in db().list_graphs() if g.startswith("kb_")]


@app.post("/api/ask")
def api_ask(body: Ask, request: Request):
    if limited(request.client.host if request.client else "?"):
        raise HTTPException(429, "demo rate limit reached, try again later")
    graph_name("kb", body.tenant)  # validates tenant id
    return ask(body.tenant, body.question)


@app.get("/api/overview")
def overview(tenant: str = "falkordb"):
    g = kb(tenant)
    stats = {l: ro(g, f"MATCH (n:{l}) RETURN count(n)")[0][0] for l in ("Person", "PR", "File", "Module", "Decision")}
    people = ro(g, "MATCH (p:Person) WHERE p.pagerank IS NOT NULL RETURN p.login, p.community, p.pagerank, p.acts ORDER BY p.acts DESC LIMIT 120")
    keep = {p[0] for p in people}
    links = [r for r in ro(g, "MATCH (a:Person)-[c:COLLAB]->(b:Person) WHERE c.n >= 2 RETURN a.login, b.login, c.n") if r[0] in keep and r[1] in keep]
    return {"stats": stats, "nodes": [{"id": a, "community": b, "pagerank": c, "acts": d} for a, b, c, d in people],
            "edges": [{"source": a, "target": b, "n": n} for a, b, n in links]}


@app.get("/api/risk")
def risk(tenant: str = "falkordb", repo: str | None = None):
    return {"bus_factor": tools.bus_factor(tenant, repo)["data"], "bridges": tools.bridges(tenant)["data"]}


@app.get("/api/eval")
def evaluation():
    f = ROOT / "data" / "eval_result.json"
    return json.loads(f.read_text()) if f.exists() else {}


app.mount("/", StaticFiles(directory=ROOT / "web", html=True), name="web")
