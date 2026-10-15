# Recording the Keystone demo video: complete guide

## What the rules say

The Graph Hacks rules require "a demo video showing the working project" (rule 10). **No maximum length, format or hosting is specified.** First Commit, WeMakeDevs' earlier event, used 3 minutes and told judges there is no live demo, so the video is the demo.

**Target 3:00. Never go over 4:00.** Judges watch many videos; the first 30 seconds decide how closely they pay attention. Put your strongest proof early (the reasoning trail and the 93% result).

Upload to **YouTube as Unlisted or Public** (anyone with the link must be able to watch without logging in). Test the link in a private window.

## Part 1: Equipment and tools (free)

| Need | Recommendation |
|---|---|
| Screen + face recorder | **OBS Studio** (free). One scene: your screen full-size with your webcam as a small rounded bubble bottom-right. A second scene: webcam full-frame for the intro and outro. |
| Microphone | Audio matters more than video. A headset or wired earbuds with a mic close to your mouth beats a laptop mic. |
| Editing | **Clipchamp** (built into Windows 11, free) or the OBS recording trimmed with it. |
| Camera | Laptop webcam is fine. Put it at eye level (stack books under the laptop). |
| Light | Sit facing a window or lamp. Never have the light behind you. |
| Resolution | 1920x1080, 30 fps, MP4. |

OBS settings: Settings > Video: base and output 1920x1080, 30 fps. Settings > Output > Recording: format MP4, quality "High" or "Indistinguishable". Settings > Audio: mic only; turn desktop audio **off** (so notification sounds are not recorded). Do a 20-second test and watch it back.

## Part 2: Prepare your screen

1. Open the live site in a **new Incognito window** so you get a fresh anonymous user with empty memory: https://keystone-graph.vercel.app
2. Press F11 for full screen, zoom 100% (Ctrl+0). Hide the bookmarks bar. Close every other tab and window.
3. Windows: turn on Focus assist / Do not disturb so no notifications appear.
4. Never show your `.env`, any token, your email, or DevTools. Keep the OpenAI and GitHub settings pages closed.
5. In a second (non-recorded) window, open the sandbox repo issues page: https://github.com/srinjoy356/keystone-sandbox/issues so you can show the created issue.
6. Tell me before you record and I will clear the shared task queue so the Act section starts empty.
7. Put your script on a second screen or phone, not on the recorded screen.
8. Do one full rehearsal. Answers take 3 to 8 seconds; you will fill that time by narrating what the steps list shows.

## Part 3: The structure (about 3:00)

| Time | Shot | Goal |
|---|---|---|
| 0:00 - 0:15 | **Face, full frame** | Who you are, the problem, the promise |
| 0:15 - 0:40 | Screen: hero, then the knowledge map | The problem on real data (Track 3) |
| 0:40 - 1:25 | Screen: Ask section, including exploring the graph | An answer with evidence you can explore (Track 1) |
| 1:25 - 1:50 | Screen: Remember | Memory that changes answers (Track 2) |
| 1:50 - 2:15 | Screen: Act | Two agents and a real action (Tracks 1 and 2) |
| 2:15 - 2:40 | Screen: Trust | Proof it works |
| 2:40 - 2:55 | Screen: How it works | FalkorDB is central |
| 2:55 - 3:05 | **Face, full frame** | Close and links |

If you are not comfortable doing it in one take, record three pieces (face intro, screen with voice-over, face outro) and join them in Clipchamp.

## Part 4: The script (say it in your own words; this is a guide)

**0:00 Face (look into the camera lens, not the screen)**
"Hi, I'm Srinjoy. Every engineering team has modules that only one person really understands, and when that person leaves, the knowledge leaves with them. I built Keystone on FalkorDB to find those modules and to explain every answer it gives. In three minutes I'll show you all three tracks."

**0:15 Screen: hero, then scroll slowly to the knowledge map**
"This is FalkorDB's own codebase: seven repositories and over four and a half thousand pull requests, loaded into a FalkorDB graph. Each tile is a module. Warm tiles mean one person holds most of the history. In the docs repo, one person holds eighty-nine percent of one module. That is Track 3, the company brain: ownership, expertise and knowledge risk, from real history."
*Action: hover one hot tile so the tooltip shows. Do not click yet.*

**0:40 Ask (scroll to section 02, click the starter "Who should review FalkorDB/GraphRAG-SDK#328?")**
While it runs: "Watch the steps. The agent chooses one of nine fixed graph tools, runs Cypher on FalkorDB, then writes the answer. It never writes a query and never sees the database."
When the answer and trail appear: "Here is why it answered this way. This pull request touched fifty files. The graph walked to earlier pull requests that touched the same files, and to the people on them. A thicker line means a bigger contribution."
*Explore the graph (about 12 seconds). Click the card for the first person in the trail (for example Naseem77):* "And it is not a picture. Click a person and I get facts straight from FalkorDB." *Click "Expand neighbours" on the card; the view switches to the Graph tab and animates in more nodes. Hover one node so the rest fade:* "Expanding runs a live read-only query and pulls in their top modules and recent pull requests. Hover highlights the connections."
*Click the Cypher tab:* "And this is the exact Cypher that ran, read-only. That is Track 1: an agent acting on connected data, with its reasoning visible and explorable."
(Optional, 5 seconds, only if you are under time: "The same tools are available over MCP.")

**1:25 Remember (scroll to section 03)**
*Click Ask, then Mark on leave, then Ask again.*
"Memory lives in the graph. Every user gets their own FalkorDB graph. I tell it the top reviewer is on leave; it writes a rule. Same question, different answer, and it tells me why. That is episodic, semantic and procedural memory, isolated from every other user. That is Track 2."

**1:50 Act (scroll to section 04)**
*Click Run triage, Claim next task, then Approve. Click the link to the created issue.*
"Two agents coordinate through the graph. A triage agent queues open pull requests; a router claims one with a single atomic write. I tested twelve threads racing for thirty tasks, and each task was claimed exactly once. When I approve, it opens a real issue in our sandbox repository. It never touches the project it analyses."

**2:15 Trust (scroll to section 05)**
"Does it work? I hid the real reviewers of five hundred and forty-two later pull requests and predicted them using only earlier history. Keystone puts a real reviewer in its top three ninety-three percent of the time. File history gets eighty-seven, vector search alone eighty-two. And the model is never trusted: it proposes decisions with quotes, and code keeps only the ones whose quote appears verbatim in the source. Twenty-seven percent were rejected. The docs repo is our weak spot, at sixty-five percent, and we say so."

**2:40 How it works (scroll to section 06)**
"Everything lives in FalkorDB: Cypher traversals, PageRank and betweenness, a vector index for decisions, a named graph per user and per tenant, read-only queries. Take FalkorDB away and nothing runs."

**2:55 Face**
"The live demo, code and README are linked below; it runs with docker compose up. I built it with Claude Code, disclosed in the README, and I can walk you through every query. Thanks for watching."

## Part 5: Delivery tips

- Speak slightly slower than normal; smile in the intro. Pauses are fine, you will trim them.
- Say "Track one, two, three" out loud. Judges score per track and this lets them tick boxes.
- Show one thing per sentence. Move the mouse slowly and point at what you are describing.
- Do not read the screen text aloud; explain what it means.
- If an answer is slow, keep talking about what the steps list shows ("it is choosing a tool, now it is running Cypher").
- If something fails, stop, take a breath, redo that section. Do not apologise on camera; cut it.
- Do two or three takes. The second is usually best.
- **Graph exploration tips:** the detail card opens at the top right of the right-hand panel. "Expand neighbours" needs the live backend, so rehearse it once; it takes about a second. Move the mouse slowly onto one node so the fade-out effect is visible on the recording. Zoom with the + and - buttons (plain scroll scrolls the page; ctrl+scroll also zooms).
- **If you run long, cut in this order:** the MCP sentence, the "Naseem77 is on leave for two weeks" plain-English chip, the click-through to the created issue. Never cut the trail, the graph exploration, the Cypher tab, the memory before-and-after, or the 93% result.

## Part 6: If the live site is slow or fails during recording

- The page falls back to a cached snapshot for reads and shows a banner; questions need the live backend.
- Retry once. If it is still slow, record that section later and cut it in.
- Last resort: run it locally with `docker compose up` (needs your OpenAI key in the shell) and record http://localhost:8000. The page is identical.

## Part 7: Edit and export

1. Trim dead air and mistakes in Clipchamp. Speed up long waits to 1.5x only if needed.
2. Optional: auto-captions (Clipchamp does this). Many judges watch muted.
3. Export 1080p MP4. Keep under 4:00.

## Part 8: Publish

- **Title:** `Keystone: know who knows, and why it was decided | FalkorDB Graph Hacks`
- **Description:**
  ```
  Keystone turns a codebase's real history into a FalkorDB graph and answers who should review, who knows what, where knowledge is at risk, and why a decision was made, with the evidence for every answer.
  Tracks: 1 Agents That Act on Connected Data, 2 Agent Memory and Coordination, 3 Company Brain.
  Live demo: https://keystone-graph.vercel.app
  Code: https://github.com/srinjoy356/keystone
  0:00 Intro  0:15 Problem  0:40 Ask  1:20 Remember  1:50 Act  2:15 Trust  2:40 How it works
  ```
- Visibility: **Unlisted** (or Public). Open the link in a private window to confirm it plays.
- Give me the URL. I will add it to `public/config.json` (the page then shows an embedded player and a "Watch the 3-minute demo" button) and to the README. Paste the same URL into the WeMakeDevs submission.

## Checklist before you press record

- [ ] Incognito window, full screen, 100% zoom, other tabs closed, notifications off
- [ ] Sandbox issues page open in another window
- [ ] Mic tested, face lit from the front
- [ ] Script on a second screen
- [ ] Rehearsed once, under 3:15
- [ ] I have cleared the shared queue (message me)
