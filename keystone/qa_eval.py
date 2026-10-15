"""Question-level eval.
1) Tool routing: does the agent pick the right tool for natural questions?
2) Decision retrieval: for sampled verified decisions, an LLM writes a natural question WITHOUT the decision's wording;
   does why_decision return the decision's source PR/issue in its top results?   python -m keystone.qa_eval [tenant]"""
import json, random, statistics, sys, time
from pathlib import Path
from openai import OpenAI
from .agent import ask
from .config import env
from .db import kb, ro
from .tools import why_decision

OUT = Path(__file__).resolve().parent.parent / "data" / "qa_eval.json"
ROUTING = [
    ("Who should review FalkorDB/GraphRAG-SDK#328?", "suggest_reviewers"),
    ("Suggest reviewers for FalkorDB/falkordb-py#150", "suggest_reviewers"),
    ("Which parts of the codebase would lose the most knowledge if one person left?", "bus_factor"),
    ("Where do we have a single point of knowledge failure?", "bus_factor"),
    ("Who understands the query planner best?", "who_knows"),
    ("Who should I ask about vector index problems?", "who_knows"),
    ("Who owns the graph/src/runtime directory?", "who_knows"),
    ("Why did the team decide to run redis-server as a non-root user?", "why_decision"),
    ("What was the reasoning behind deduplicating entities in GraphRAG?", "why_decision"),
    ("How did we end up with the current approach to storing vectors?", "why_decision"),
    ("Which contributors connect the different repositories together?", "bridges"),
    ("Who are the key bridge people between teams?", "bridges"),
    ("How are gkorland and galshubeli connected?", "connection"),
    ("What is the shortest link between AviAvni and Naseem77?", "connection"),
]


def routing(tenant):
    ok, rows = 0, []
    for q, want in ROUTING:
        used = [t["tool"] for t in ask(tenant, q)["trace"]]
        hit = want in used
        ok += hit
        rows.append({"q": q, "want": want, "used": used, "ok": hit})
        print(("OK  " if hit else "MISS"), want, "<-", used, q, flush=True)
    return {"accuracy": ok / len(ROUTING), "n": len(ROUTING), "rows": rows}


def retrieval(tenant, n=40, seed=3):
    g, c = kb(tenant), OpenAI(api_key=env("OPENAI_API_KEY"))
    rows = ro(g, "MATCH (d:Decision)-[:DECIDED_IN]->(s) RETURN d.text, d.why, s.id, s.title")
    random.Random(seed).shuffle(rows)
    hits, ranks, ms = 0, [], []
    for text, why, sid, title in rows[:n]:
        q = c.chat.completions.create(model=env("OPENAI_MODEL", "gpt-4o-mini"), temperature=0, messages=[{"role": "user", "content":
            f"A new engineer wants to know the reasoning behind this engineering decision. Write ONE natural question they would ask. "
            f"Do not reuse the decision's distinctive wording, do not mention PR numbers.\nDecision: {text}\nReason: {why}"}]).choices[0].message.content.strip()
        t = time.time()
        res = why_decision(tenant, q, k=5)["data"]["decisions"]
        ms.append((time.time() - t) * 1000)
        pos = next((i for i, d in enumerate(res) if d["pr"] == sid), None)
        hits += pos is not None
        ranks.append(pos)
    found = [r + 1 for r in ranks if r is not None]
    return {"recall@5": hits / n, "mrr": sum(1 / r for r in found) / n, "n": n, "median_ms": round(statistics.median(ms))}


if __name__ == "__main__":
    tenant = next((a for a in sys.argv[1:] if not a.startswith("--")), "falkordb")
    prev = json.loads(OUT.read_text()) if OUT.exists() else {}
    res = {"routing": prev["routing"] if "--retrieval-only" in sys.argv and prev else routing(tenant), "retrieval": retrieval(tenant)}
    print({k: {m: v for m, v in r.items() if m != "rows"} for k, r in res.items()})
    OUT.write_text(json.dumps(res, indent=1))
