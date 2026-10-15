"""Concurrent read benchmark of the real tools (no LLM): python tests/bench.py [threads] [requests]"""
import random, statistics, sys, time
from concurrent.futures import ThreadPoolExecutor
from keystone import tools
from keystone.db import kb, ro

T = "falkordb"
threads, total = int(sys.argv[1]) if len(sys.argv) > 1 else 16, int(sys.argv[2]) if len(sys.argv) > 2 else 400
g = kb(T)
prs = [r[0] for r in ro(g, "MATCH (pr:PR)<-[:AUTHORED]-(:Person) WHERE pr.changedFiles > 0 RETURN pr.id LIMIT 300")]
mods = [r[0].split(":", 1)[1] for r in ro(g, "MATCH (m:Module) WHERE m.path <> '/' RETURN m.id LIMIT 200")]
random.seed(1)
jobs = [("suggest_reviewers", lambda: tools.suggest_reviewers(T, random.choice(prs))),
        ("who_knows", lambda: tools.who_knows(T, random.choice(mods))),
        ("bus_factor", lambda: tools.bus_factor(T)),
        ("connection", lambda: tools.connection(T, "gkorland", "galshubeli"))]
lat, errs = {n: [] for n, _ in jobs}, 0


def one(i):
    global errs
    name, fn = jobs[i % len(jobs)]
    t = time.time()
    try:
        fn()
        lat[name].append((time.time() - t) * 1000)
    except Exception as e:
        errs += 1
        print("ERR", name, str(e)[:100])


t0 = time.time()
with ThreadPoolExecutor(threads) as ex:
    list(ex.map(one, range(total)))
dt = time.time() - t0
print(f"{total} calls, {threads} threads, {total / dt:.0f} calls/s, errors={errs}")
for n, v in lat.items():
    if v:
        v.sort()
        print(f"{n:18} n={len(v):3} p50={statistics.median(v):6.0f}ms p95={v[int(len(v) * .95) - 1]:6.0f}ms max={v[-1]:6.0f}ms")
