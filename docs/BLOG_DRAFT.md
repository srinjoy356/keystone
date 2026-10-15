# The reviewer nobody asked for: a knowledge-risk graph on FalkorDB

*Draft for the Graph Hacks blog prize. Rewrite it in your own voice; keep the numbers, the failures and the limits section, they are what make it credible. Replace the bracketed bits.*

Every team has a module that one person understands. Nobody notices until that person is on leave, or has moved on, and a pull request sits unreviewed for a week because the three people who could have reviewed it are not who the CODEOWNERS file says they are.

We built Keystone to answer four questions from a codebase's real history: who should review this, who actually knows this module, which modules would lose knowledge if one person left, and why was it decided that way. It is a FalkorDB graph of 7 repositories (4,620 PRs, 2,351 issues, 338 contributors, 1,634 extracted decisions) with an agent on top. Every answer shows its subgraph and the Cypher behind it. [live link] [repo link]

## The problem is not text search

"Who should review this PR?" sounds like a retrieval problem until you write down what the answer needs: this PR touches 50 files, each file belongs to a directory, each directory has a parent, every earlier PR in those directories was authored or reviewed by someone, recency matters, and the people who reviewed this author before matter too. That is five hops. In Cypher it is one query.

```cypher
UNWIND $mods AS mid
MATCH up = (m0:Module {id: mid})-[:PARENT*0..2]->(m:Module)
WITH m, min(length(up)) AS k
MATCH (m)<-[:PARENT*0..3]-(:Module)<-[:IN]-(:File)<-[:TOUCHES]-(pr:PR)<-[r:AUTHORED|REVIEWED]-(p:Person)
WHERE pr.createdAt < $asof AND p.login <> $author
RETURN p.login, sum(... * exp(-($asof - pr.createdAt) / $tau) / (1.0 + k)) AS s
```

## How we knew it worked (and where it did not)

We did not want to demo a nice-looking answer. So we hid every merged PR's reviewers and asked each method to predict them using only history before the PR was opened, on a test slice that nothing was tuned on. 542 PRs across the 7 repos:

| Method | hit@1 | hit@3 | MRR |
|---|---|---|---|
| Most popular reviewers | 0.25 | 0.79 | 0.52 |
| Recent reviewers | 0.40 | 0.89 | 0.64 |
| File history (blame / CODEOWNERS style) | 0.50 | 0.87 | 0.68 |
| Vector only (embed title + paths) | 0.48 | 0.82 | 0.65 |
| **Keystone** | **0.57** | **0.93** | **0.75** |

hit@3 beats file history by 5.9 points (95% bootstrap CI 3.5 to 8.1). It is not magic: on the docs repository, where reviewers rotate, it reaches only 0.65. On a tiny repo where one maintainer reviews everything, every method scores near 1.0 and the comparison means nothing, which is why we ran the evaluation only after loading the large repos.

## What fought back

* **A module signal that tuned itself out.** We built a module-hierarchy signal we loved. The tuner gave it weight zero on this data. We kept it for the "who knows this module" tool and stopped paying for it in reviewer scoring, which cut p50 latency from 561 ms to 178 ms under 16 concurrent callers.
* **Community detection collapsed.** Label propagation on the collaboration graph produced one big blob and a pile of singletons: the core team is that tightly connected. We stopped forcing it, coloured the network by each person's home repo, and used betweenness to find the people who actually bridge repos.
* **`shortestPath` is directed only.** Our "how are A and B connected" query failed until we added directed derived edges (`KNOWS`, `KNOWN_BY`, `LINKS`) so the path could alternate person -> module -> person.
* **`RO_QUERY` on a graph that does not exist yet errors.** Every first-time user hit it. Memory graphs are now created on first use.
* **Two ideas that made things worse, and we threw them out.** Adding the PR title to decision embeddings dropped retrieval recall@5 from 0.73 to 0.48. Fusing decision search with PR-title search left recall flat and lowered MRR. And we tried to have an LLM mark which decisions superseded which: on a sample we read by hand, about one in three was right, mostly "newer decision adds detail". We replaced it with a dated list of related decisions in the same module and let the reader judge.
* **Silence is the expensive failure.** The LLM proposes a decision with a quote. Our code keeps it only if the quote is a verbatim substring of the cited message and a second check confirms the quote states the decision. About three in ten proposals were rejected. Without that gate, the very first answer we tested "explained" a design choice from a question someone asked in a review comment.

## Memory that changes what the agent does

Tell Keystone "Naseem77 is on leave for two weeks" and the agent writes an expiring rule into your own FalkorDB graph; the next reviewer suggestion skips them and says why. Say "they are back" and the rule is deleted. Every user has a separate graph (`mem_<user>`), so isolation is structural, not a filter someone has to remember to write. Two agents (a triage agent and router workers) coordinate through task nodes in a shared graph; claiming is one write query, and a test races 12 threads for 30 tasks and asserts each is claimed exactly once.

## Honest limits

* It predicts who *did* review, which is a proxy for who *should*.
* Risk is computed per module, never per person; names are public GitHub handles.
* The action step is a dry run unless a write token and an allowlisted repo are configured.
* Decision extraction covers the most-discussed threads, not every PR.
* We have not measured time saved for any real team.

## Try it

`docker compose up` gives you the app and a FalkorDB preloaded with both tenants (FalkorDB's repos and `pallets/click` + `pallets/flask`). `python -m keystone.build_tenant <tenant> owner/repo ...` builds a new isolated graph from any public repos. An MCP server exposes the same tools to Claude Desktop or Cursor.

*Built with Claude Code as the coding assistant, disclosed in the README; the team is responsible for and can explain every query and design decision.*
