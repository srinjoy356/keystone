"""Temporal-holdout eval: predict who actually reviewed each merged PR using only history before it was opened.
Weights are tuned on a validation slice and reported on a later, untouched test slice."""
import itertools, json, sys
from pathlib import Path
import numpy as np
from .db import kb
from .github import iter_prs
from .load import pr_rows
from .queries import signals, repo_signal

CACHE = Path(__file__).resolve().parent.parent / "data" / "eval_signals.json"
TAUS = (90, 365)


def cases(repo: str):
    out = []
    for p in iter_prs(repo):
        r = pr_rows(repo, p)
        truth = {x["u"] for x in r["reviews"]}
        if p["mergedAt"] and r["author"] and truth and r["files"]:
            out.append({"id": r["pr"]["id"], "repo": repo, "author": r["author"], "asof": r["pr"]["createdAt"],
                        "files": [f["id"] for f in r["files"]], "truth": sorted(truth)})
    return sorted(out, key=lambda c: c["asof"])


def gather(tenant: str, repos: list[str]) -> list[dict]:
    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    g, allc = kb(tenant), []
    for repo in repos:
        cs = cases(repo)
        for i, c in enumerate(cs):
            if c["id"] not in cache:
                cache[c["id"]] = {str(t): {**signals(g, c["files"], c["author"], c["asof"], t),
                                           "repo": repo_signal(g, repo, c["author"], c["asof"], t)} for t in TAUS}
            c["sig"] = cache[c["id"]]
        CACHE.write_text(json.dumps(cache))
        for k, c in enumerate(cs):
            c["split"] = "train" if k < 0.5 * len(cs) else "val" if k < 0.7 * len(cs) else "test"
        allc += cs
        print(repo, len(cs), "cases", flush=True)
    return allc


def rank(c, w, tau):
    s = c["sig"][str(tau)]
    tot: dict[str, float] = {}
    for name, wt in w.items():
        d = s[name]
        mx = max(d.values(), default=0) or 1
        for u, v in d.items():
            tot[u] = tot.get(u, 0) + wt * v / mx
    return sorted(tot, key=lambda u: (-tot[u], u))


def metrics(cs, w, tau):
    h1, h3, h5, rr = [], [], [], []
    for c in cs:
        r, t = rank(c, w, tau), set(c["truth"])
        pos = next((i for i, u in enumerate(r) if u in t), None)
        h1.append(pos == 0); h3.append(pos is not None and pos < 3); h5.append(pos is not None and pos < 5)
        rr.append(1 / (pos + 1) if pos is not None else 0)
    return {"hit@1": np.mean(h1), "hit@3": np.mean(h3), "hit@5": np.mean(h5), "mrr": np.mean(rr), "n": len(cs),
            "_h3": h3}


BASELINES = {  # (weights, tau)
    "recent-reviewers (repo prior)": ({"repo": 1}, 90),
    "popular-reviewers (all-time)": ({"repo": 1}, 365),
    "file-history (CODEOWNERS/blame-style)": ({"file": 1}, 365),
}


def run(tenant="falkordb", repos=None):
    repos = repos or sys.argv[1:]
    allc = gather(tenant, repos)
    val = [c for c in allc if c["split"] == "val"]
    test = [c for c in allc if c["split"] == "test"]
    grid = itertools.product((0, 0.5, 1, 2), repeat=4)
    best = max(((dict(zip(("file", "module", "social", "repo"), g)), tau) for g in grid if any(g) for tau in TAUS),
               key=lambda wt: metrics(val, *wt)["mrr"])
    print("tuned on", len(val), "val PRs ->", best)
    rows = {k: metrics(test, *v) for k, v in BASELINES.items()}
    rows["KEYSTONE (graph blend)"] = metrics(test, *best)
    print(f"\nTEST on {len(test)} later PRs")
    for k, m in rows.items():
        print(f"{k:42} hit@1={m['hit@1']:.2f} hit@3={m['hit@3']:.2f} hit@5={m['hit@5']:.2f} mrr={m['mrr']:.2f}")
    rng = np.random.default_rng(0)
    a, b = np.array(rows["KEYSTONE (graph blend)"]["_h3"], float), np.array(rows["file-history (CODEOWNERS/blame-style)"]["_h3"], float)
    d = [np.mean((a - b)[rng.integers(0, len(a), len(a))]) for _ in range(2000)]
    print(f"hit@3 gain vs file-history: {np.mean(a - b):+.3f}  95% CI [{np.percentile(d, 2.5):+.3f}, {np.percentile(d, 97.5):+.3f}]")
    out = {"best": {"w": best[0], "tau": best[1]}, "n_val": len(val), "n_test": len(test),
           "test": {k: {m: float(v) for m, v in r.items() if not m.startswith("_")} for k, r in rows.items()}}
    (CACHE.parent / "eval_result.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    run(repos=sys.argv[1:])
