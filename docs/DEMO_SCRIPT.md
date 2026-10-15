# Keystone: 3-minute demo script

The site is one scrolling story: **Problem, Ask, Remember, Act, Trust, How it works**. Record the live site (https://keystone-graph.vercel.app) at 1080p, browser zoom 100%, in a fresh window so you get a clean memory graph. Use the top navigation to jump between sections; talk through any wait (an answer takes 3 to 8 seconds).

**Before recording:** open the site once and click "Trust" so everything is warm. If you did the memory or handoff steps while testing, press "Reset demo" and "Start over". Check the sandbox repo for old test issues (the demo creates one real GitHub issue when you press Approve).

## 0:00 - 0:20  Hook (hero)
"Every engineering team has modules only one person understands. When that person leaves, the knowledge goes too. Keystone loads a codebase's real history into a FalkorDB graph, and an agent on top answers who should review, who knows what, where knowledge is at risk, and why decisions were made. I loaded FalkorDB's own repositories: 4,620 pull requests, 2,220 decisions with sources."
* Point at the hero card: the example answer beside its evidence graph.

## 0:20 - 0:50  1. Problem
* Scroll to **The problem**. "Each tile is a module, colour is how much of its history one person holds. These warm tiles are real: in falkordb-browser, one person holds 55 to 61% of two modules and was last active five months ago, with no active backup."
* Click the **Who works with whom** toggle for two seconds ("PageRank and betweenness from FalkorDB's own algorithms"), then back to the map.
* Click a red tile (for example the docs `_includes` one). The page scrolls to Ask and runs the question.

## 0:50 - 1:25  2. Ask
* "I never wrote a query. The agent picked a graph tool; this graph is exactly the evidence."
* Click the **How it was found** tab: "Here is the exact Cypher, read-only, with row counts."
* Click the chip **Who should review FalkorDB/GraphRAG-SDK#328?** Show the answer and click a node to open the PR on GitHub. Say: "It walks pull request, files, earlier pull requests, people, weighted by recency."

## 1:25 - 2:00  3. Remember
* Scroll to **Remember**. Click **Ask**: show the four names. Click **Mark ... on leave**. Click **Ask again**.
* "Same question, a different answer, and it tells me why. The rule lives in my own graph, mem underscore my id. Nobody else's graph can see it. It also stores what I asked and what I approve or reject."
* Optional (if time): click the chip "Naseem77 is on leave for two weeks" to show it works from plain English.

## 2:00 - 2:30  4. Act
* Scroll to **Act**. Click **Run triage**, **Claim next task**, then **Approve**.
* "Two agents share this queue through the graph. Claiming a task is one atomic write; I tested twelve threads racing for thirty tasks and each task was claimed exactly once. On approval it opens a real issue in our sandbox repo." Click the link to the created issue.

## 2:30 - 2:55  5. Trust
* Scroll to **Trust**. "I hid the real reviewers of 542 later pull requests and predicted them using only earlier history. Keystone puts a real reviewer in its top three 93% of the time, against 87% for file history and 82% for vector search alone; the gain is 5.9 points with a confidence interval above zero."
* Point at the funnel: "An LLM proposes decisions with quotes; code keeps one only if the quote is verbatim in the source. 27% were thrown away." Point at "What we do not claim".

## 2:55 - 3:00  Close
"Everything lives in FalkorDB: Cypher, algorithms, vector search, one graph per user and tenant. It works on any public repo with one command, and an MCP server lets other agents use the same tools."

## Cut list if you run long
Network toggle, the plain-English memory chip, the click-through to the created issue. Never cut the Evidence graph, the Cypher view, the memory before/after, or the 93% result.
