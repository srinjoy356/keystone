"""Manual smoke run of every tool against the local graph (prints timing + head of result)."""
import json, sys, time
from keystone import tools

CASES = [("who_knows", ("falkordb", "graphrag")),
         ("suggest_reviewers", ("falkordb", "FalkorDB/GraphRAG-SDK#328")),
         ("bus_factor", ("falkordb",)),
         ("bridges", ("falkordb",)),
         ("connection", ("falkordb", "galshubeli", "swilly22")),
         ("why_decision", ("falkordb", "why did we avoid storing vectors"))]
for name, args in CASES:
    t = time.time()
    try:
        r = tools.TOOLS[name](*args)
        print(f"{name} {time.time() - t:.2f}s", json.dumps(r["data"], ensure_ascii=True)[:360])
    except Exception as e:
        print(f"{name} FAIL {type(e).__name__}: {str(e)[:200]}")
