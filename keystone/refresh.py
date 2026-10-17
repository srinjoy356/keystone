"""Incremental refresh: pull only what changed on GitHub since the last refresh, upsert it into the tenant graph,
re-extract decisions for the new threads, and recompute the derived layer.
    python -m keystone.refresh <tenant> [--cloud] [--dry-run] [--no-decisions] [--since YYYY-MM-DD]
--cloud updates the live FalkorDB Cloud graph (the deployed site reads it directly); without it the local Docker graph is updated.
Safe to repeat: every write is a MERGE."""
import json, os, sys, time
from . import decisions, embed_prs, github, load, load_decisions
from .db import kb, ro
from .derive import derive

OVERLAP = 3600  # re-read the last hour of the previous run so nothing slips between runs
DAY = 86400


def repos_of(g) -> list[str]:
    return [r[0] for r in ro(g, "MATCH (r:Repo) RETURN r.name ORDER BY r.name")]


def watermark(g, repo: str) -> int:
    """Where to resume. After a refresh: its start time. Before any refresh: the newest PR we hold, minus a day
    (the original load happened after that PR was opened, so this is a safe superset)."""
    r = ro(g, "MATCH (r:Repo {name:$n}) RETURN r.refreshedAt", {"n": repo})
    if r and r[0][0]:
        return int(r[0][0]) - OVERLAP
    m = ro(g, "MATCH (p:PR {repo:$n}) RETURN max(p.createdAt)", {"n": repo})
    return int(m[0][0] or 0) - DAY


def refresh(tenant: str, dry_run: bool = False, with_decisions: bool = True, since_override: int = 0) -> dict:
    g, started, summary = kb(tenant), int(time.time()), {}
    for repo in repos_of(g):
        since = since_override or watermark(g, repo)
        prs = github.fetch_updated(repo, since, "pullRequests")
        issues = github.fetch_updated(repo, since, "issues")
        pids = [f"{repo}#{p['number']}" for p in prs]
        iids = [f"{repo}#{i['number']}" for i in issues]
        known = dict(ro(g, "MATCH (p:PR) WHERE p.id IN $ids RETURN p.id, p.state", {"ids": pids})) if pids else {}
        iknown = {r[0] for r in ro(g, "MATCH (i:Issue) WHERE i.id IN $ids AND i.url IS NOT NULL RETURN i.id", {"ids": iids})} if iids else set()
        s = summary[repo] = {"since": time.strftime("%Y-%m-%d %H:%M", time.gmtime(since)), "prs_seen": len(prs),
                             "new_prs": sum(1 for x in pids if x not in known),
                             "state_changes": sum(1 for p, x in zip(prs, pids) if x in known and known[x] != p["state"]),
                             "issues_seen": len(issues), "new_issues": sum(1 for x in iids if x not in iknown), "new_decisions": 0}
        if dry_run:
            continue
        n_dec = lambda: ro(g, "MATCH (d:Decision)-[:DECIDED_IN]->(x) WHERE x.id STARTS WITH $p RETURN count(d)", {"p": repo + "#"})[0][0]
        before = n_dec()
        if prs:
            load.load_prs(tenant, repo, prs)
        if issues:
            load.load_issue_nodes(tenant, repo, issues)
        if with_decisions:
            for kind, items, ids in (("prs", prs, pids), ("issues", issues, iids)):
                if items:
                    decisions.run(repo, kind=kind, items=items)
                    load_decisions.load(tenant, repo, kind, only=set(ids))
            s["new_decisions"] = n_dec() - before
    if not dry_run:
        derive(tenant)
        embed_prs.embed_prs(tenant)
        for repo in summary:
            g.query("MATCH (r:Repo {name:$n}) SET r.refreshedAt=$t", {"n": repo, "t": started})
        g.query("MERGE (m:Meta {id:'refresh'}) SET m.at=$t, m.summary=$s", {"t": started, "s": json.dumps(summary)})
    return summary


if __name__ == "__main__":
    if "--cloud" in sys.argv:  # the db connection is created lazily, so this must be set before the first query
        os.environ["FALKORDB_TARGET"] = "cloud"
    argv, since = sys.argv[1:], 0
    if "--since" in argv:  # look further back than the watermark, e.g. for a dry-run demo
        i = argv.index("--since")
        since = int(time.mktime(time.strptime(argv[i + 1], "%Y-%m-%d")))
        del argv[i:i + 2]
    args = [a for a in argv if not a.startswith("--")]
    res = refresh(args[0], "--dry-run" in argv, "--no-decisions" not in argv, since)
    for repo, s in res.items():
        print(f"{repo:34} new PRs {s['new_prs']:3}  state changes {s['state_changes']:3}  PRs seen {s['prs_seen']:3}  new issues {s['new_issues']:3}  new decisions {s['new_decisions']:3}  (since {s['since']} UTC)")
    print("dry run, nothing written" if "--dry-run" in sys.argv else "refreshed")
