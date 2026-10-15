# Understand Keystone: read this before anything else

This is your study guide. It assumes you know basic programming but not graph databases. Read it in order. It takes about 60 to 90 minutes. At the end there is a self-test; if you can answer those questions out loud, you can defend this project to any judge.

The rule you must satisfy: "participants must be able to explain what was built and why", including the graph model, the queries, the architecture and the technical decisions. This file is organised around exactly those four things.

---

## 0. The 30-second pitch (memorise this)

"Every engineering team has modules that only one person really understands. When that person leaves or goes quiet, the knowledge goes with them. Keystone loads a codebase's real public history (pull requests, reviews, issues) into a FalkorDB graph, and puts an agent on top that answers who should review this, who actually knows this module, which modules are at risk, and why a decision was made. Every answer shows the subgraph and the exact Cypher behind it, and every quoted decision is checked by code against the source text. On 542 held-out pull requests it picks a real reviewer in its top three 93% of the time, against 87% for the standard file-history approach."

---

# PART 1: What is FalkorDB

## 1.1 What a graph database is

A normal (relational) database stores rows in tables. A graph database stores two things:

* **Nodes** (things): a person, a pull request, a file. Each node has a **label** (its type) and **properties** (key-value data), for example `(:Person {login: "gkorland"})`.
* **Relationships** (connections between nodes): "this person AUTHORED this pull request". A relationship has a **direction**, a **type**, and optional properties, for example `(:Person)-[:AUTHORED]->(:PR)`.

The point: **the connections are stored as first-class data**, so following them is cheap. Asking "who reviewed pull requests that touched the same files as this pull request" in SQL needs several joins across big tables. In a graph it is a walk: PR -> files -> other PRs -> people.

A mental picture of our data:

```
(Person gkorland) -[AUTHORED]-> (PR #276) -[TOUCHES]-> (File graph/src/x.rs) -[IN]-> (Module graph/src)
(Person Naseem77) -[REVIEWED]-> (PR #276)
```

## 1.2 Why a graph here, and not SQL or a vector database

* **SQL** can do it, but "walk up to a parent directory, then down to everything under it, then to the people" is a recursive multi-join that is awkward to write and slow to run.
* **A vector database** finds text that is *similar*. It cannot tell you who is connected to what through five hops, or that one person holds 89% of a module's history. Similarity is not structure.
* **A graph** stores structure directly. We also use vectors (see 1.4) for the "enter by meaning" step, then graph traversal for the "expand by structure" step. That combination is what FalkorDB itself calls hybrid retrieval.

Our evaluation proves the point: a vector-only baseline got 82% (hit@3), our graph blend got 93%.

## 1.3 What FalkorDB specifically is

* An open-source graph database, formerly RedisGraph. It runs **as a module inside Redis**. That is why you connect to it with a Redis client on port 6379 and send commands like `GRAPH.QUERY`. Our Python code uses the official `falkordb` client, which wraps Redis.
* It stores the graph **in memory** and traverses it using sparse-matrix linear algebra (their CTO talks about "linear-algebra graph modeling"). The practical result is very fast multi-hop queries.
* It speaks **openCypher**, the most common graph query language (the same family as Neo4j's Cypher).
* It is **multi-graph**: one server holds many separate named graphs. A query on graph `kb_falkordb` physically cannot see graph `kb_pallets`. We use this for isolation (see 3.9).
* **Built-in graph algorithms** you call from Cypher: PageRank, betweenness centrality, label propagation (community detection), shortest paths, and more.
* **Vector index** (HNSW) on node properties, so you can store embeddings and do nearest-neighbour search in the same database as the graph.
* **Read-only queries**: the command `GRAPH.RO_QUERY` rejects any write at the server. We use it for everything the agent can run.
* **FalkorDB Cloud** is the hosted version. Our live site uses the free tier (100 MB). The Docker image (`falkordb/falkordb`) is the self-hosted version we use for development and in our own container.

Version note you should know: the local image we pulled reported FalkorDB module version 42201 (the 4.22.x line). FalkorDB announced 6.0 (a Rust rewrite) on its blog on Sept 29. We did not verify which engine the Cloud free tier runs; our code only uses features that exist in both. If a judge asks, say that.

## 1.4 Cypher in ten minutes

Cypher draws the pattern you want with ASCII art. Everything we do is a variation of these.

| You want | Cypher |
|---|---|
| Find nodes | `MATCH (p:Person {login: "gkorland"}) RETURN p` |
| Follow a relationship | `MATCH (p:Person)-[:AUTHORED]->(pr:PR) RETURN pr.title` |
| Filter | `... WHERE pr.createdAt < $asof AND p.login <> $author` |
| Several relationship types | `-[r:AUTHORED\|REVIEWED]->` (the `\|` means "either") |
| Variable-length path | `-[:PARENT*0..3]->` (follow PARENT zero to three times) |
| Count / sum / group | `RETURN p.login, count(DISTINCT pr), sum(...)` (anything not aggregated is the group key) |
| Create or update safely | `MERGE (p:Person {login: $u})` (create only if missing; "idempotent") |
| Bulk load | `UNWIND $rows AS r MERGE (...)` (loop over a list parameter) |
| Parameters | `$name` placeholders; values are passed separately, never pasted into the string (this prevents injection) |
| Call an algorithm | `CALL algo.pageRank('Person','COLLAB') YIELD node, score` |
| Vector search | `CALL db.idx.vector.queryNodes('Decision','emb',5,vecf32($v)) YIELD node, score` |
| Shortest path | `shortestPath((a)-[:LINKS*..6]->(b))` (FalkorDB: directed only) |

Two FalkorDB-specific facts we hit and you should remember: `shortestPath` only works on directed relationships, so we built directed derived edges; and `GRAPH.RO_QUERY` on a graph that does not exist yet throws an error, so we create memory graphs on first use.

---

# PART 2: What Keystone is and what it does

## 2.1 The problem

Knowledge in a software team is concentrated and invisible. Concretely, four questions are hard to answer today:

1. **Who should review this pull request?** CODEOWNERS files go stale.
2. **Who actually knows this module?** The person named in a doc may not have touched it in a year.
3. **Where would we lose knowledge if one person left?** Nobody measures it.
4. **Why was this decided?** The reason is buried in a review thread from two years ago.

## 2.2 What it does (the demo, feature by feature)

| Feature | What you see | Where it lives |
|---|---|---|
| Ask the agent | Type a question, get an answer with an evidence graph and the exact Cypher used | `agent.py`, `tools.py` |
| Reviewer suggestions | Names plus the earlier PRs that justify each | `suggest_reviewers` in `tools.py` |
| Who knows X | For a path (`graph/src/runtime`) or a free-text topic ("variable-length traversal") | `who_knows` |
| Problem section | Tile map of modules coloured by how concentrated knowledge is, plus top risks | `bus_factor`, `risk_map` |
| Bridge people | People connecting otherwise separate groups | `bridges` (betweenness) |
| Connection | "How are A and B connected?" as a path | `connection` (shortest path) |
| Why was it decided | A decision, a verbatim quote, a link to the source thread, and dated related decisions | `why_decision` |
| Remember section | A three-step demo plus a panel of what is stored; or tell it "Naseem77 is on leave for two weeks"; it skips them and explains | `mem.py`, `remember_unavailable` |
| Act section | Triage agent queues open PRs; router workers claim and propose; you approve; an issue is created in a sandbox repo | `coord.py` |
| Trust section | The held-out reviewer-prediction results and the decision-verification funnel | `evaluate.py`, `facts.py` |
| MCP server | The same tools usable from Claude Desktop or Cursor | `mcp_server.py` |
| Two tenants | FalkorDB's repos and pallets/click + flask, each its own graph | `build_tenant.py` |

## 2.3 How it maps to the three tracks

* **Track 1, Agents That Act on Connected Data:** the agent chooses among graph tools (multi-hop scoring, PageRank, betweenness, shortest path), exposes them over MCP, shows explainable evidence, and on approval takes a real action (opens an issue in our own sandbox repo, never in the analysed project).
* **Track 2, Agent Memory and Coordination:** working memory (last turns), episodic memory (past questions linked to entities), semantic memory (accept/reject feedback), procedural memory (expiring avoid rules, also writable in plain English), one graph per user, and a two-agent task queue with an atomic claim.
* **Track 3, Company Brain:** people, modules, PRs and issues in one graph; ownership and expertise; decisions traced to their source thread with verified quotes; knowledge-risk per module.

## 2.4 The data

Public GitHub data only: 7 FalkorDB repositories (4,620 PRs, 2,351 issue nodes, 343 people) and pallets/click + pallets/flask as a second tenant (1,560 PRs, 605 issue nodes, 1,301 people). After extraction: 2,220 decisions (FalkorDB) and 983 (pallets). We store only public handles, no emails.

---

# PART 3: How we built it

Think of it as a pipeline with five stages. Each stage is a file you can open.

```
GitHub  ->  github.py  ->  load.py  ->  derive.py  ->  tools.py  ->  agent.py  ->  api.py + UI
(raw)       (cache)        (graph)      (algorithms)    (queries)     (LLM)        (browser)
                              |
                      decisions.py -> load_decisions.py (LLM-extracted, code-verified)
```

## 3.1 Stage 1: fetch (`keystone/github.py`)

Uses GitHub's GraphQL API to page through pull requests newest to oldest, 30 at a time, with files, reviews, comments and linked issues in one query. It writes each page to `data/raw/...` so reruns never refetch (resumable, cached). It watches the rate limit and sleeps if it runs low. The same file fetches issues.

Decision to remember: bots are dropped later (in `load.py`), not here, so the cache stays a faithful copy of GitHub.

## 3.2 Stage 2: load into the graph (`keystone/load.py`)

This defines our **graph data model**. Know this table cold.

| Node label | Meaning | Key properties |
|---|---|---|
| `Person` | A GitHub user (human only) | `login`; later `pagerank`, `bridge`, `community`, `home`, `acts` |
| `PR` | A pull request | `id` like `owner/repo#123`, `title`, `createdAt` (epoch seconds), `state`, `changedFiles` |
| `Issue` | An issue (our "tickets" source) | `id`, `title`, `url`, `state` |
| `File` | A file path in a repo | `id`, `path` |
| `Module` | A directory, up to 3 levels deep | `id` like `owner/repo:src/runtime` |
| `Repo` | A repository | `name` |
| `Decision` | An extracted decision | `text`, `why`, `quote`, `ts`, `emb` (512-number vector), `kind` |

| Relationship | Meaning |
|---|---|
| `(Person)-[:AUTHORED]->(PR)` | opened the PR |
| `(Person)-[:REVIEWED]->(PR)` | submitted a review (state: APPROVED etc.) |
| `(Person)-[:COMMENTED]->(PR\|Issue)` | commented but did not review |
| `(PR)-[:TOUCHES]->(File)` | PR changed that file |
| `(File)-[:IN]->(Module)` | file lives in that directory |
| `(Module)-[:PARENT]->(Module)` | directory hierarchy |
| `(PR)-[:CLOSES]->(Issue)` | PR closes that issue |
| `(Decision)-[:DECIDED_IN]->(PR\|Issue)` | where the decision was made |
| `(Person)-[:STATED]->(Decision)` | who said the quote |

Important details:
* Everything is loaded with `MERGE`, so loading twice changes nothing (idempotent). A test and a rerun prove it.
* Bots (`__typename == "Bot"`) and deleted accounts are excluded; authors never count as their own reviewers (see `pr_rows`, covered by `tests/test_units.py`).
* Timestamps are stored as integer epoch seconds so Cypher can do arithmetic on them.
* `Module` is the directory chain capped at three levels (`modules_of`), so "src/a/b/c/d.py" belongs to `src`, `src/a`, `src/a/b`.

## 3.3 Stage 3: derived layer and algorithms (`keystone/derive.py`)

After loading, we compute extra structure inside FalkorDB itself:

* `COLLAB`: an edge from a PR author to each reviewer/commenter, with a count. This is "who works with whom".
* `KNOWS` / `KNOWN_BY`: person <-> module edges where a person touched a module in at least 3 PRs. Directed both ways on purpose, because FalkorDB's `shortestPath` is directed-only.
* `LINKS`: a symmetric person-to-person link (both directions).
* **PageRank** over `COLLAB`: a person's "reviewing authority" (people reviewed by many get a higher score).
* **Betweenness** over `LINKS`: how often a person lies on shortest paths between others. High betweenness = a bridge between groups.
* **Label propagation** over `LINKS`: community detection. On this data it collapsed into one big community plus tiny ones (the core team is very tightly connected), so for the UI we colour people by `home` (the repo where most of their activity is).

## 3.4 Stage 4: the scoring queries (`keystone/queries.py`, `keystone/tools.py`)

This is the heart. Learn the idea, then the formula.

**The idea:** to suggest reviewers for a PR, look at *history strictly before the PR was opened* (`$asof`), and score every person by how much they authored or reviewed work touching the same files, with recent work counting more.

**The query for the file signal** (`FILE_SIGNAL`):

```cypher
MATCH (f:File) WHERE f.id IN $files
MATCH (p:Person)-[r:AUTHORED|REVIEWED]->(pr:PR)-[:TOUCHES]->(f)
WHERE pr.createdAt < $asof AND p.login <> $author
RETURN p.login, sum((CASE type(r) WHEN 'REVIEWED' THEN $wr ELSE $wa END)
                    * exp(-($asof - pr.createdAt) / $tau)) AS s
```

Read it as: "for each file in this PR, find every earlier PR that touched it, find the people attached, weight a review (`$wr` = 1.0) more than an authorship (`$wa` = 0.5), multiply by a recency decay `exp(-age / tau)`, and add it up per person."

* `exp(-age/tau)` is **exponential decay**: work from `tau` seconds ago counts about 37% as much as work today. We use tau = 90 days.
* The **social signal** (`SOCIAL_SIGNAL`) adds people who reviewed *this author's* earlier PRs, with the same decay.
* We **blend** the signals: normalise each to its maximum, then take a weighted sum. The weights were **tuned on a separate validation slice** by grid search: file 2.0, social 0.5, tau 90 days. The module-hierarchy signal got weight 0 on this data, so reviewer suggestion skips computing it (it is still used by "who knows this module").
* Weak candidates (under 15% of the top score) are dropped instead of listed, so we do not pad lists.

**Topic expertise** (hybrid, `who_knows` with free text): embed the topic, find the 40 nearest PRs by vector similarity (`db.idx.vector.queryNodes` on `PR.emb`), then in the same query walk to the people who authored or reviewed those PRs, weighting by similarity and recency. Vector = enter by meaning; graph = expand by structure.

**Knowledge risk** (`_module_stats` / `bus_factor`): for each module with at least 10 PR touches in the last 12 months, take the person with the most touches. If they hold 40% or more, and no one else holds at least 15% and was active in the last 120 days, the module is "concentrated". It is a statement about **modules, not people**.

**Shortest path** (`connection`): `shortestPath((a)-[:KNOWS|KNOWN_BY|LINKS*..6]->(b))`, over the directed derived edges.

## 3.5 Stage 5: decisions with proof (`decisions.py`, `load_decisions.py`)

An LLM is good at reading a discussion and bad at being trusted. So we split the job:

1. **LLM proposes:** for threads with enough discussion, gpt-4o-mini returns up to 3 decisions, each with a verbatim `quote` and the id of the message it came from.
2. **Code verifies (check 1):** the quote must be a **verbatim substring** (whitespace-normalised) of the cited message. Else it is rejected.
3. **Second check:** another LLM call asks only "does this quote *by itself* state this decision, rather than ask about it or describe something unrelated?" Unsupported ones are rejected.
4. **Only survivors are stored**, with an embedding of "decision. reason", so they can be searched by meaning.

Result: 27% of everything the LLM proposed (1,168 of 4,371) was thrown away. This is the single most defensible design decision in the project: **the model never gets to assert a fact the code cannot check against the source.**

`why_decision` then does vector search over decisions and one graph hop to the source thread and speaker, and also returns dated "earlier related" and "later related" decisions touching the same module. These are explicitly chronology, not a claim that one replaced another (we tried an LLM "supersedes" judge; about one in three was right, so we dropped it).

## 3.6 The agent (`keystone/agent.py`)

A bounded loop (max 4 rounds) using OpenAI function calling:

1. Send the question, a system prompt and the nine tool definitions to `gpt-4o-mini`.
2. If the model asks for a tool, we run **our** Python function (never model-written Cypher) and feed back the JSON result.
3. Repeat, then the model writes the final plain-text answer.

Safety properties (these are what a security-minded judge will probe):
* **The model never writes Cypher and never sees the database.** It only picks tool names and arguments.
* Arguments are filtered to each function's real parameters; `user` identity is injected from the session, never taken from the model.
* All tool reads run through `ro()` in `db.py`: parameterised, time-limited, `GRAPH.RO_QUERY`.
* The system prompt says text inside tool results (PR titles, quotes) is **data from strangers**, never instructions (prompt-injection defence).
* Every call is logged (`QUERY_LOG`), which is how the UI shows the exact Cypher, row counts and timings.

The nine tools: `who_knows`, `suggest_reviewers`, `bus_factor`, `bridges`, `connection`, `why_decision`, `recall_memory`, `remember_unavailable`, `forget_unavailable`.

## 3.7 Memory (`keystone/mem.py`)

Each user gets **their own graph**, named `mem_<user>`. Inside:

* **Episodic:** `Episode` nodes (a past question and answer) linked to the entities (`Entity`) it touched.
* **Semantic:** `FEEDBACK` edges (accept or reject) from the user to people.
* **Procedural:** `AVOID` edges: "skip this person under this module prefix until this date". They are created by pressing "skip them" **or** by telling the agent in plain English ("Naseem77 is on leave for two weeks"). The next `suggest_reviewers` applies the rule, drops that person, and returns a note the agent reads out.
* **Working memory:** the last three chat turns are sent with each request (in the browser, not stored).

Isolation is structural: user A's rules live in a different graph from user B's. There is no `WHERE user = ...` filter anyone could forget.

## 3.8 Coordination and action (`keystone/coord.py`)

Two cooperating agents share state in the graph `ops_<tenant>`:

* **Triage agent:** finds open PRs, checks whether their files sit in at-risk modules, and creates a `Task` node per PR with a priority.
* **Router workers:** call `claim`, which is **one write query**: `MATCH (t:Task {status:'queued'}) WITH t ORDER BY ... LIMIT 1 SET t.status='claimed' ...`. FalkorDB serialises writes, so two workers cannot claim the same task. `tests/test_coord.py` proves it by racing 12 threads for 30 tasks.
* A human approves. The **executor** then opens a real issue in `srinjoy356/keystone-sandbox` with the recommendation and evidence links. It never writes to the projects being analysed. It is capped at 10 per day (counter stored in FalkorDB) and falls back to a dry run without a token.

## 3.9 Isolation: tenants and users (`keystone/db.py`)

* Tenant graph: `kb_<tenant>`; user graph: `mem_<user>`; ops graph: `ops_<tenant>`.
* `graph_name()` only accepts `[A-Za-z0-9_-]{1,40}`, so a user cannot escape the namespace (tested).
* `tests/test_isolation.py` proves tenants share no nodes, tools only see their own tenant, the read path rejects writes, and one user's memory is invisible to another.

## 3.10 The API and UI (`keystone/api.py`, `public/index.html`)

FastAPI serves the JSON endpoints and the single-page UI (plain HTML plus Cytoscape.js for graphs, no build step). Guardrails for a public demo: input patterns on every field, a per-visitor rate limit (reads `X-Forwarded-For` because Vercel is a proxy), and a **global daily cap** on LLM calls stored in FalkorDB so it holds across serverless instances (protects your OpenAI bill).

## 3.11 MCP server (`keystone/mcp_server.py`)

Exposes the six read-only tools over the Model Context Protocol (MCP) via stdio. Claude Desktop or Cursor can list and call them. This is the "MCP tool selection" focus of Track 1.

## 3.12 How we measured it (`evaluate.py`, `qa_eval.py`)

**Reviewer prediction (the headline result).** For each merged PR with at least one human reviewer, we ask each method to predict the reviewers using only history before the PR was opened (`$asof`). The PRs are split by time: first 50% train, next 20% validation (tune weights here), last 30% test (report here, untouched). Metrics: hit@k (a real reviewer in the top k) and MRR (average of 1/rank of the first correct reviewer).

| Method | hit@1 | hit@3 | MRR |
|---|---|---|---|
| Most popular reviewers | 0.25 | 0.79 | 0.52 |
| Recent reviewers in repo | 0.40 | 0.89 | 0.64 |
| File history (CODEOWNERS/blame style) | 0.50 | 0.87 | 0.68 |
| Vector only (no graph) | 0.48 | 0.82 | 0.65 |
| **Keystone** | **0.57** | **0.93** | **0.75** |

542 test PRs. The gain over file history is +5.9 points on hit@3, with a 95% bootstrap confidence interval of +3.5 to +8.1 (it excludes zero). Why this is honest: time split (no peeking at the future), weights tuned on separate data, strong baselines, and it is reported per repo including the weak case (docs, 0.65, where the main reviewer changed over time).

**Agent questions.** Tool routing: the agent picked the right tool on 14 of 14 test questions. Decision retrieval: for 40 decisions, an LLM wrote a question *without reusing the decision's wording*; the source was in the top 5 for 70%.

**Speed.** `tests/bench.py`: 16 threads, 400 calls, zero errors, about 190 calls per second; reviewer suggestion p50 178 ms, p95 343 ms (one laptop, local database; treat as order of magnitude).

## 3.13 Packaging and deployment

* `Dockerfile` + `docker-compose.yml`: one image with FalkorDB, the app and **preloaded graphs** (`seed/dump.rdb.gz`). `docker compose up` gives judges everything, with the FalkorDB Browser on port 3000 to inspect the graph.
* **Live site:** Vercel (function region Mumbai, next to the database) + FalkorDB Cloud free tier. Entry point `app.py`; config `vercel.json`. Secrets are Vercel environment variables, never in the repo.
* `build_tenant.py`: one command turns any public repos into a new isolated tenant.

## 3.14 What failed (your best stories; judges love them)

* **Module signal tuned itself out.** We built a module-hierarchy signal; the tuner gave it weight 0. We stopped paying for it in reviewer scoring, which cut latency a lot.
* **Community detection collapsed** into one blob. We coloured by home repo instead and used betweenness for bridges.
* **`shortestPath` is directed-only** in FalkorDB; we added directed derived edges.
* **Two retrieval ideas made things worse** (adding the PR title to embeddings; rank-fusing two searches), so we reverted them.
* **LLM supersession detection was about one-in-three accurate**, so we dropped it for an honest timeline.
* **Quote verification** rejected 27% of the model's proposals, including a "decision" it inferred from a question.
* **A crowded graph** (your screenshot): we reworked layout and labels.

## 3.15 Honest limits (say these before a judge finds them)

* It predicts who *did* review, a proxy for who *should*.
* Knowledge risk is per module, not per person; handles are public.
* Decision extraction covers the most-discussed threads, not every PR; precision of extracted decisions is checked for source fidelity, not for importance.
* The docs repo is weak (0.65) because of reviewer turnover over time.
* The Cloud free tier connects without TLS; only public data is stored.
* We have not measured time saved for a real team.
* The real action writes to a sandbox repo, by design.

---

# PART 4: Likely judge questions, with answers

1. **Why FalkorDB and not just Postgres plus pgvector?** The core question is multi-hop and weighted over structure (PR to files to directories to earlier PRs to people). In SQL that is recursive joins; in Cypher it is one pattern. We also use graph algorithms (PageRank, betweenness) and per-tenant and per-user graph isolation natively. Remove FalkorDB and every one of those capabilities goes with it.
2. **Where exactly does the graph do real work?** Reviewer scoring, risk map, topic expertise (vector recall then graph expansion), bridges, shortest path, memory rules, the task queue's atomic claim. Open "How it was found" in the Ask section to see the queries.
3. **How do you know it works?** Time-split held-out evaluation on 542 PRs, tuned on separate data, against four baselines, with a bootstrap confidence interval, reported per repo including the weak one.
4. **Can the LLM hallucinate a decision?** It can propose one, but code keeps it only if the quote is a verbatim substring of the cited message and a second check confirms the quote states the decision. 27% of proposals were rejected.
5. **Does the model write Cypher? Can it write to the database?** No. It picks from nine fixed tools. All reads run with `GRAPH.RO_QUERY`, parameterised and time-limited, so the server itself rejects writes. The only writes (memory, task queue) are our own code, scoped to the user's or tenant's graph.
6. **What about prompt injection from PR text?** Tool results are treated as data by the system prompt; the model cannot choose a user identity; the worst a malicious comment can do is influence wording, since every tool is read-only except writing to the caller's own memory.
7. **How does memory work, and is it really memory?** Four layers: working (last turns), episodic (past questions linked to entities), semantic (accept/reject feedback), procedural (expiring avoid rules). A rule changes the next answer, and you can see it in the Remember section. Each user has a separate graph.
8. **How do two agents coordinate safely?** Through shared graph state. Claiming a task is one write query and FalkorDB serialises writes; a test races 12 threads for 30 tasks and asserts each is claimed exactly once.
9. **Is it multi-tenant?** Yes, structurally. Different graphs per tenant and per user. Tests prove no shared nodes and that tools stay inside their tenant.
10. **What does "acts" mean here?** On human approval it opens a real issue in our sandbox repo with the recommendation and evidence. It deliberately never writes to the projects it analyses.
11. **Why gpt-4o-mini?** Cost and speed, and the design makes the model replaceable: it only explains tool output. Quality comes from the graph and the verification, not the model.
12. **What would you do with more time?** Cover more decision threads, add Discord/Slack as a chat source, per-repo model tuning for drift (the docs repo), and measure time saved with a real team.
13. **Did AI write this?** Yes, Claude Code wrote most of the code, disclosed in the README. We designed the problem, chose the graph model, directed the evaluation, and can explain every query and decision (this guide exists for that reason).
14. **Is the data legal and public?** Public GitHub metadata and discussion from public repositories; short quotes with links; no emails, no private data.
15. **What was the hardest bug?** Pick one of 3.14. The best is the quote-verification story or the module signal that tuned itself out.

---

# PART 5: Cheat sheet

Run it:
```bash
docker compose up --build          # everything preloaded, http://localhost:8000
python -m keystone.build_tenant NAME owner/repo ...   # new tenant from any public repos
uvicorn keystone.api:app --port 8000
PYTHONPATH=. pytest -q tests       # 12+ tests
PYTHONPATH=. python -m keystone.evaluate <repos>      # reproduce the main result
python -m keystone.mcp_server      # MCP over stdio
```

Where things are:
* Data model: `keystone/load.py` (`STMTS`, `modules_of`, `pr_rows`)
* Scoring Cypher: `keystone/queries.py`, `keystone/tools.py`
* Algorithms: `keystone/derive.py`
* Decisions: `keystone/decisions.py`
* Agent: `keystone/agent.py` (read `SYSTEM`, `SPECS`, `ask`)
* Memory: `keystone/mem.py`; queue: `keystone/coord.py`
* Tests: `tests/test_units.py`, `test_coord.py`, `test_isolation.py`, `test_api.py`

Glossary:
* **Node / relationship / label / property:** thing / connection / its type / its data.
* **Cypher:** the graph query language. **openCypher:** its open standard.
* **MERGE:** create if not exists (idempotent). **UNWIND:** loop over a list.
* **Traversal / hop:** following relationships. **Multi-hop:** several in a row.
* **PageRank:** importance from incoming links. **Betweenness:** how often a node lies on shortest paths. **Label propagation:** community detection.
* **Embedding / vector index:** a list of numbers capturing meaning; an index for nearest-neighbour search.
* **hit@k:** a true answer appears in the top k. **MRR:** average of 1 over the rank of the first correct answer.
* **Idempotent:** doing it twice equals doing it once.
* **MCP:** Model Context Protocol, a standard way for AI clients to call tools.
* **Tenant:** an isolated customer or dataset (here, a separate graph).
* **Concept drift:** the true pattern changes over time (docs reviewers changed).

---

# PART 6: Self-test (answer out loud, then check the section)

1. Draw the graph model from memory: six node labels and the relationships between them. (3.2)
2. Explain `exp(-(asof - createdAt)/tau)` and why `$asof` matters. (3.4)
3. Why are `KNOWS` and `KNOWN_BY` both directed? (3.3, 1.4)
4. What exactly happens, step by step, when I ask "Who should review PR X?" (3.4, 3.6)
5. How does a decision get from a GitHub comment to the screen, and what can reject it? (3.5)
6. Why can't the model damage the database? (3.6)
7. How can two workers never claim the same task? (3.8)
8. How was the 93% measured, and why should I believe it? (3.12)
9. Name two things that failed and what you did about them. (3.14)
10. What does the project NOT claim? (3.15)

If you can do all ten without reading, you are ready. If you get stuck on one, tell me the number and I will go through it with you in detail.
