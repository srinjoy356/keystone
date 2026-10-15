"""Cypher the product depends on. All read-only, parameterised, time-travelling via $asof (epoch seconds)."""
from .db import ro

# S1: people who authored/reviewed earlier PRs that touched the SAME files, recency-decayed.
FILE_SIGNAL = """
MATCH (f:File) WHERE f.id IN $files
MATCH (p:Person)-[r:AUTHORED|REVIEWED]->(pr:PR)-[:TOUCHES]->(f)
WHERE pr.createdAt < $asof AND p.login <> $author
RETURN p.login, sum((CASE type(r) WHEN 'REVIEWED' THEN $wr ELSE $wa END) * exp(-($asof - pr.createdAt) / $tau)) AS s
"""

# S2: module hierarchy. Walk up from each touched module (nearer ancestor = stronger), then down to every
# file under that ancestor, then to the people who worked on PRs touching them.
MODULE_SIGNAL = """
UNWIND $mods AS mid
MATCH up = (m0:Module {id: mid})-[:PARENT*0..2]->(m:Module)
WITH m, min(length(up)) AS k
MATCH (m)<-[:PARENT*0..3]-(:Module)<-[:IN]-(:File)<-[:TOUCHES]-(pr:PR)<-[r:AUTHORED|REVIEWED]-(p:Person)
WHERE pr.createdAt < $asof AND p.login <> $author
RETURN p.login, sum((CASE type(r) WHEN 'REVIEWED' THEN $wr ELSE $wa END) * exp(-($asof - pr.createdAt) / $tau) / (1.0 + k)) AS s
"""

# S3: social proximity. Who has reviewed this author's earlier PRs (author -> reviewer edges derived on the fly).
SOCIAL_SIGNAL = """
MATCH (a:Person {login: $author})-[:AUTHORED]->(pr:PR)<-[:REVIEWED]-(p:Person)
WHERE pr.createdAt < $asof AND p.login <> $author
RETURN p.login, sum(exp(-($asof - pr.createdAt) / $tau)) AS s
"""

MODS_OF_FILES = "MATCH (f:File)-[:IN]->(m:Module) WHERE f.id IN $files RETURN DISTINCT m.id"

DAY = 86400


def signals(g, files: list[str], author: str, asof: int, tau_days: float = 180, wr: float = 1.0, wa: float = 0.5):
    p = {"files": files, "author": author, "asof": asof, "tau": tau_days * DAY, "wr": wr, "wa": wa}
    mods = [r[0] for r in ro(g, MODS_OF_FILES, p)]
    return {"file": dict(ro(g, FILE_SIGNAL, p)),
            "module": dict(ro(g, MODULE_SIGNAL, {**p, "mods": mods})),
            "social": dict(ro(g, SOCIAL_SIGNAL, p))}

# S4: repo-level prior. Who has been reviewing in this repo lately.
REPO_SIGNAL = """
MATCH (:Repo {name: $repo})<-[:IN_REPO]-(pr:PR)<-[:REVIEWED]-(p:Person)
WHERE pr.createdAt < $asof AND p.login <> $author
RETURN p.login, sum(exp(-($asof - pr.createdAt) / $tau)) AS s
"""


def repo_signal(g, repo: str, author: str, asof: int, tau_days: float = 180):
    return dict(ro(g, REPO_SIGNAL, {"repo": repo, "author": author, "asof": asof, "tau": tau_days * DAY}))
