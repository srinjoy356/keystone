"""Write verified decisions into the graph with embeddings (vector index on Decision.emb)."""
import hashlib, json, sys
from openai import OpenAI
from .config import env
from .db import kb
from .decisions import OUT

DIM = 512


def embed(texts: list[str]) -> list[list[float]]:
    c = OpenAI(api_key=env("OPENAI_API_KEY"))
    out = []
    for i in range(0, len(texts), 100):
        r = c.embeddings.create(model=env("OPENAI_EMBED_MODEL", "text-embedding-3-small"), input=texts[i:i + 100], dimensions=DIM)
        out += [d.embedding for d in r.data]
    return out


def load(tenant: str, repo: str, kind: str = "prs") -> int:
    g = kb(tenant)
    try:
        g.query(f"CREATE VECTOR INDEX FOR (d:Decision) ON (d.emb) OPTIONS {{dimension:{DIM}, similarityFunction:'cosine'}}")
        g.query("CREATE INDEX FOR (d:Decision) ON (d.id)")
    except Exception as e:
        if "already indexed" not in str(e).lower():
            raise
    data = json.loads((OUT / (repo.replace("/", "__") + ("" if kind == "prs" else "__issues") + ".json")).read_text())
    rows = []
    for pid, v in data.items():
        for d in v["decisions"]:
            did = hashlib.sha1(f"{pid}|{d['quote']}".encode()).hexdigest()[:12]
            rows.append({"id": did, "pr": pid, "text": d["decision"], "why": d.get("rationale", ""), "quote": d["quote"],
                         "who": d["who"], "ts": v["createdAt"]})
    if not rows:
        return 0
    embs = embed([f"{r['text']}. {r['why']}" for r in rows])
    for r, e in zip(rows, embs):
        r["emb"] = e
    for i in range(0, len(rows), 50):
        for label in ("PR", "Issue"):  # a decision's source is a PR thread or an issue (ticket) thread
            g.query(f"""UNWIND $rows AS r MATCH (src:{label} {{id:r.pr}})
                       MERGE (d:Decision {{id:r.id}}) SET d.text=r.text, d.why=r.why, d.quote=r.quote, d.ts=r.ts, d.emb=vecf32(r.emb), d.kind='{label}'
                       MERGE (d)-[:DECIDED_IN]->(src)
                       WITH d, r MATCH (p:Person {{login:r.who}}) MERGE (p)-[:STATED]->(d)""", {"rows": rows[i:i + 50]})
    return len(rows)


if __name__ == "__main__":
    kind = "issues" if sys.argv[2] == "--issues" else "prs"
    for repo in sys.argv[3 if kind == "issues" else 2:]:
        print(repo, load(sys.argv[1], repo, kind))
