"""Idempotent load of cached PRs into the tenant graph (MERGE only, safe to re-run)."""
import sys
from datetime import datetime, timezone
from .db import kb, db, graph_name
from .github import iter_prs

INDEXES = ["Person(login)", "PR(id)", "File(id)", "Module(id)", "Issue(id)", "Repo(name)"]


def ts(iso: str | None) -> int | None:
    return int(datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()) if iso else None


def human(a) -> str | None:
    return a["login"] if a and a.get("login") and a.get("__typename") != "Bot" else None


def modules_of(repo: str, path: str) -> list[str]:
    """Directory chain up to 3 levels, shallow->deep. Top-level files belong to '<repo>:/'."""
    dirs = path.split("/")[:-1][:3]
    return [f"{repo}:/"] if not dirs else [f"{repo}:" + "/".join(dirs[: i + 1]) for i in range(len(dirs))]


def pr_rows(repo: str, pr: dict) -> dict:
    pid, author = f"{repo}#{pr['number']}", human(pr["author"])
    reviews: dict[str, str] = {}
    for r in pr["reviews"]["nodes"]:
        u = human(r["author"])
        if u and u != author:
            reviews[u] = r["state"] if reviews.get(u) != "APPROVED" else "APPROVED"
    comments = {u for c in pr["comments"]["nodes"] if (u := human(c["author"])) and u != author and u not in reviews}
    files = []
    for f in pr["files"]["nodes"]:
        chain = modules_of(repo, f["path"])
        files.append({"id": f"{repo}:{f['path']}", "path": f["path"], "mod": chain[-1], "chain": chain,
                      "adds": f["additions"], "dels": f["deletions"]})
    return {"pr": {"id": pid, "repo": repo, "number": pr["number"], "title": pr["title"], "url": pr["url"],
                   "state": pr["state"], "createdAt": ts(pr["createdAt"]), "mergedAt": ts(pr["mergedAt"]),
                   "changedFiles": pr["changedFiles"], "adds": pr["additions"], "dels": pr["deletions"]},
            "author": author, "reviews": [{"u": u, "s": s} for u, s in reviews.items()],
            "comments": sorted(comments), "files": files,
            "issues": [{"id": f"{repo}#{i['number']}", "title": i["title"]} for i in pr["closingIssuesReferences"]["nodes"]]}


STMTS = {
 "people": "UNWIND $rows AS u MERGE (:Person {login:u})",
 "prs": """UNWIND $rows AS r MERGE (pr:PR {id:r.pr.id}) SET pr += r.pr
           MERGE (repo:Repo {name:r.pr.repo}) MERGE (pr)-[:IN_REPO]->(repo)
           WITH r, pr WHERE r.author IS NOT NULL MERGE (a:Person {login:r.author}) MERGE (a)-[:AUTHORED]->(pr)""",
 "reviews": """UNWIND $rows AS r MATCH (pr:PR {id:r.pr}) MATCH (p:Person {login:r.u})
               MERGE (p)-[x:REVIEWED]->(pr) SET x.state=r.s""",
 "comments": "UNWIND $rows AS r MATCH (pr:PR {id:r.pr}) MATCH (p:Person {login:r.u}) MERGE (p)-[:COMMENTED]->(pr)",
 "files": """UNWIND $rows AS r MATCH (pr:PR {id:r.pr})
             MERGE (f:File {id:r.id}) SET f.path=r.path
             MERGE (m:Module {id:r.mod}) SET m.repo=r.repo, m.path=r.modpath
             MERGE (f)-[:IN]->(m) MERGE (pr)-[t:TOUCHES]->(f) SET t.adds=r.adds, t.dels=r.dels""",
 "parents": """UNWIND $rows AS r MERGE (c:Module {id:r.c}) MERGE (p:Module {id:r.p}) MERGE (c)-[:PARENT]->(p)""",
 "issues": "UNWIND $rows AS r MATCH (pr:PR {id:r.pr}) MERGE (i:Issue {id:r.id}) SET i.title=r.title MERGE (pr)-[:CLOSES]->(i)",
}


def ensure_indexes(g):
    for ix in INDEXES:
        label, prop = ix[:-1].split("(")
        try:
            g.query(f"CREATE INDEX FOR (n:{label}) ON (n.{prop})")
        except Exception as e:  # already exists
            if "already indexed" not in str(e).lower():
                raise


def load_repo(tenant: str, repo: str, batch: int = 100) -> dict:
    g = kb(tenant)
    ensure_indexes(g)
    rows = [pr_rows(repo, p) for p in iter_prs(repo)]
    people = sorted({x for r in rows for x in ([r["author"]] if r["author"] else []) + [v["u"] for v in r["reviews"]] + r["comments"]})
    g.query(STMTS["people"], {"rows": people})
    for i in range(0, len(rows), batch):
        b = rows[i:i + batch]
        g.query(STMTS["prs"], {"rows": b})
        g.query(STMTS["reviews"], {"rows": [{"pr": r["pr"]["id"], **v} for r in b for v in r["reviews"]]})
        g.query(STMTS["comments"], {"rows": [{"pr": r["pr"]["id"], "u": u} for r in b for u in r["comments"]]})
        g.query(STMTS["files"], {"rows": [{"pr": r["pr"]["id"], "repo": repo, "id": f["id"], "path": f["path"], "mod": f["mod"],
                                           "modpath": f["mod"].split(":", 1)[1], "adds": f["adds"], "dels": f["dels"]}
                                          for r in b for f in r["files"]]})
        pars = {(f["chain"][j], f["chain"][j - 1]) for r in b for f in r["files"] for j in range(1, len(f["chain"]))}
        pars |= {(f["chain"][0], f"{repo}:/") for r in b for f in r["files"] if f["chain"][0] != f"{repo}:/"}
        g.query(STMTS["parents"], {"rows": [{"c": c, "p": p} for c, p in pars]})
        g.query(STMTS["issues"], {"rows": [{"pr": r["pr"]["id"], **i} for r in b for i in r["issues"]]})
    return {"prs": len(rows), "people": len(people)}


def stats(tenant: str) -> dict:
    g = kb(tenant)
    out = {}
    for lab in ("Person", "PR", "File", "Module", "Issue", "Repo"):
        out[lab] = g.ro_query(f"MATCH (n:{lab}) RETURN count(n)").result_set[0][0]
    out["edges"] = g.ro_query("MATCH ()-[e]->() RETURN count(e)").result_set[0][0]
    return out


if __name__ == "__main__":
    tenant = sys.argv[1]
    for repo in sys.argv[2:]:
        print(repo, load_repo(tenant, repo), flush=True)
    print(stats(tenant))
