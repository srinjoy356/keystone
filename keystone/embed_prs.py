"""Embed PRs (title + touched module names) into PR.emb with a vector index, so topic questions can enter the graph by meaning
and then expand to people by structure (hybrid retrieval)."""
import sys
from .db import kb
from .load_decisions import DIM, embed


def embed_prs(tenant: str, batch: int = 200) -> int:
    g = kb(tenant)
    try:
        g.query(f"CREATE VECTOR INDEX FOR (p:PR) ON (p.emb) OPTIONS {{dimension:{DIM}, similarityFunction:'cosine'}}")
    except Exception as e:
        if "already indexed" not in str(e).lower():
            raise
    rows = g.ro_query("""MATCH (pr:PR) WHERE pr.emb IS NULL
                         OPTIONAL MATCH (pr)-[:TOUCHES]->(:File)-[:IN]->(m:Module)
                         WITH pr, collect(DISTINCT m.id)[..6] AS mods RETURN pr.id, pr.title, mods""").result_set
    for i in range(0, len(rows), batch):
        b = rows[i:i + batch]
        texts = [f"{t} | {' '.join(x.split(':', 1)[1] for x in mods)}" for _, t, mods in b]
        g.query("UNWIND $rows AS r MATCH (pr:PR {id:r.id}) SET pr.emb = vecf32(r.e)",
                {"rows": [{"id": pid, "e": e} for (pid, _, _), e in zip(b, embed(texts))]})
    return len(rows)


if __name__ == "__main__":
    print(embed_prs(sys.argv[1]))
