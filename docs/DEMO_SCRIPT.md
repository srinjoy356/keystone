# Keystone: 3-minute demo script

Record at 1080p, browser at 100% zoom, the Keystone page full screen. Speak in your own words; the lines below are a guide. Keep every on-screen action under 5 seconds; the agent answers in 3-8 seconds, so talk through the wait.

**Before recording:** reset your memory graph (new browser profile or clear localStorage so you get a fresh user id), open the Eval tab once to warm the cache, have `docker compose up` or the live URL ready.

## 0:00 - 0:20  The problem (face or title card)
"Every team has modules only one person understands. When they leave or go quiet, so does the knowledge. Keystone builds a FalkorDB graph from a codebase's real history and puts an agent on top that tells you who knows what, why it was decided, and where knowledge is at risk. I loaded FalkorDB's own repositories: 7 repos, 4,600 PRs, 2,300 issues."

## 0:20 - 0:55  Track 3: ownership and risk (Company Brain)
* Click the chip **"Which modules are most at risk of losing knowledge?"**.
* Say: "This is not a vector search. It is a Cypher aggregation: for each module, who touched it in the last year, and does anyone else cover it."
* Switch to the **How it was found** tab. Point at the Cypher and the row counts. "Every answer shows the exact queries."
* Switch to **Risk map**: "falkordb-browser's schema and monitor modules: one person, 55-61% of the touches, last active 151 days ago. That is a real finding."

## 0:55 - 1:30  Track 1: act on connected data, explainable
* Type: **Who should review FalkorDB/GraphRAG-SDK#328 and why?**
* Show the Evidence graph. "The agent walked PR -> files -> earlier PRs -> people, weighted by recency. These edges are the justification."
* Say the result: "I tested this honestly: predict the real reviewers of 542 later PRs using only earlier history. Keystone gets the right reviewer in its top 3 for 93%, against 87% for file history and 82% for vector-only." (Open the **Eval** tab for 3 seconds.)

## 1:30 - 2:10  Track 2: memory that changes behaviour
* Type: **Naseem77 is on leave for the next two weeks. Who should review FalkorDB/GraphRAG-SDK#328 then?**
* "I told it something in plain English. It wrote a rule into my own graph, and the suggestion changed."
* Open the **Memory** tab: show the rule. "Each user has their own FalkorDB graph; nothing is shared."
* Type: **Naseem77 is back.** then re-ask: "Rule gone, suggestion restored."

## 2:10 - 2:35  Track 2: two agents, shared state
* **Handoff** tab: click **1. Triage agent**, then **2. Router agent** (twice). "Triage queues open PRs with risk notes. Router workers claim tasks with a single atomic write; I tested 12 threads racing for 30 tasks and each task was claimed exactly once." Click **Approve**: "the executor shows the exact GitHub request; it is a dry run unless a write token and an allowlisted repo are configured."

## 2:35 - 2:55  Track 3: decisions with proof
* Type: **Why did the team run redis-server as an unprivileged user in Docker?**
* "The answer quotes the maintainer verbatim and links the source. Every quote is checked by code against the original text; about 3 in 10 of what the LLM proposed was rejected."

## 2:55 - 3:00  Close
"Keystone works on any public repo with one command, includes an MCP server so other agents can use the same tools, and ships with tests. Thank you."

## Cut list if you run long
Handoff board, the Network tab, the MCP server. Never cut the Evidence graph, the Cypher trace, or the eval number.
