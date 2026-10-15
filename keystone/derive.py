"""Derived graph layer: author->reviewer COLLAB edges, then FalkorDB's own algorithms write scores onto Person."""
import sys
from .db import kb

COLLAB = """MATCH (a:Person)-[:AUTHORED]->(pr:PR)<-[:REVIEWED]-(b:Person) WHERE a <> b
WITH a, b, count(pr) AS n, max(pr.createdAt) AS last
MERGE (a)-[c:COLLAB]->(b) SET c.n = n, c.last = last"""
KNOWS = """MATCH (p:Person)-[:AUTHORED|REVIEWED]->(pr:PR)-[:TOUCHES]->(:File)-[:IN]->(m:Module)
WITH p, m, count(DISTINCT pr) AS n WHERE n >= 3
MERGE (p)-[k:KNOWS]->(m) SET k.n = n
MERGE (m)-[b:KNOWN_BY]->(p) SET b.n = n"""
# FalkorDB shortestPath is directed-only, so make the person<->person link symmetric explicitly.
LINKS = "MATCH (a:Person)-[:COLLAB]->(b:Person) MERGE (a)-[:LINKS]->(b) MERGE (b)-[:LINKS]->(a)"
ACTIVITY = """MATCH (p:Person) OPTIONAL MATCH (p)-[:AUTHORED|REVIEWED|COMMENTED]->(pr:PR)
WITH p, count(pr) AS acts, max(pr.createdAt) AS last SET p.acts = acts, p.lastActive = last"""
PAGERANK = "CALL algo.pageRank('Person','COLLAB') YIELD node, score SET node.pagerank = score"
BETWEEN = """CALL algo.betweenness({nodeLabels:['Person'], relationshipTypes:['COLLAB'], samplingSize:200, samplingSeed:7})
YIELD node, score SET node.bridge = score"""
COMMUNITY = """CALL algo.labelPropagation({nodeLabels:['Person'], relationshipTypes:['COLLAB'], maxIterations:10})
YIELD node, communityId SET node.community = communityId"""


def derive(tenant: str) -> dict:
    g = kb(tenant)
    for q in (COLLAB, KNOWS, LINKS, ACTIVITY, PAGERANK, BETWEEN, COMMUNITY):
        g.query(q)
    return {"collab_edges": g.ro_query("MATCH ()-[c:COLLAB]->() RETURN count(c)").result_set[0][0],
            "communities": g.ro_query("MATCH (p:Person) WHERE p.community IS NOT NULL RETURN count(DISTINCT p.community)").result_set[0][0]}


if __name__ == "__main__":
    print(derive(sys.argv[1]))
