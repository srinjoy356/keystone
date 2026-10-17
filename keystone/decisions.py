"""Extract engineering decisions from PR discussions. The LLM proposes, code verifies:
a decision is kept only if its quote is a verbatim substring of the cited message (else rejected and counted)."""
import json, re, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from openai import OpenAI
from .config import env
from .github import iter_prs
from .load import human, ts

OUT = Path(__file__).resolve().parent.parent / "data" / "decisions"
KW = re.compile(r"\b(because|instead of|trade-?off|decid|revert|deprecat|rather than|we should|won't|will not|breaking|rationale|why)\b", re.I)
PROMPT = """You extract engineering DECISIONS from one pull-request discussion.
A decision is an explicit choice, trade-off, rejection, or reversal about design, behaviour, scope, or process, with a reason if stated.
Rules: only decisions clearly present in the text; no speculation; a question or a request is NOT a decision; prefer the message of the person who made the choice; return {"decisions":[]} if none.
Each item: {"decision": <=25 words, "rationale": <=25 words or "", "quote": EXACT verbatim excerpt (25-220 chars) copied from ONE message, "msg": the message id like "m3"}.
Return JSON {"decisions":[...]} with at most 3 items."""


def messages(pr: dict) -> list[dict]:
    ms = [{"id": "m0", "who": human(pr["author"]) or "unknown", "text": (pr["bodyText"] or "")[:1500]}]
    for kind, key in (("review", "reviews"), ("comment", "comments")):
        for n in pr.get(key, {"nodes": []})["nodes"]:
            u = human(n["author"])
            if u and len(n["bodyText"] or "") > 40:
                ms.append({"id": f"m{len(ms)}", "who": u, "text": n["bodyText"][:1200]})
    return ms


def score(ms: list[dict]) -> int:
    return len(ms) - 1 + (3 if any(KW.search(m["text"]) for m in ms) else 0) + (2 if len(ms[0]["text"]) > 400 else 0)


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower()).strip()


def verify(ds: list[dict], ms: list[dict]) -> tuple[list[dict], int]:
    by_id, kept, rejected = {m["id"]: m for m in ms}, [], 0
    for d in ds:
        m = by_id.get(str(d.get("msg")))
        q = norm(str(d.get("quote", "")))
        if m and len(q) >= 25 and q in norm(m["text"]) and d.get("decision"):
            kept.append({**d, "who": m["who"]})
        else:
            rejected += 1
    return kept, rejected


JUDGE = """For each item, answer whether the QUOTE by itself states or clearly implies the DECISION (not merely asks about it, proposes it tentatively, or describes something unrelated).
Return JSON {"supported":[indexes that ARE supported]}."""


def judge(client, model, kept):
    if not kept:
        return kept
    items = "\n".join(f"{i}. DECISION: {d['decision']}\n   QUOTE: {d['quote']}" for i, d in enumerate(kept))
    r = client.chat.completions.create(model=model, temperature=0, response_format={"type": "json_object"},
                                       messages=[{"role": "system", "content": JUDGE}, {"role": "user", "content": items}])
    ok = set(json.loads(r.choices[0].message.content).get("supported", []))
    return [d for i, d in enumerate(kept) if i in ok]


def extract(client, model, pr, ms):
    body = f"PR title: {pr['title']}\n\n" + "\n\n".join(f"[{m['id']}] {m['who']}: {m['text']}" for m in ms)
    r = client.chat.completions.create(model=model, temperature=0, response_format={"type": "json_object"},
                                       messages=[{"role": "system", "content": PROMPT}, {"role": "user", "content": body}])
    return json.loads(r.choices[0].message.content).get("decisions", [])


def run(repo: str, limit: int | None = None, workers: int = 8, kind: str = "prs", items: list | None = None):
    limit = limit or int(env("DECISION_LIMIT", "400"))
    client, model = OpenAI(api_key=env("OPENAI_API_KEY")), env("OPENAI_MODEL", "gpt-4o-mini")
    OUT.mkdir(parents=True, exist_ok=True)
    f = OUT / (repo.replace("/", "__") + ("" if kind == "prs" else "__issues") + ".json")
    done = json.loads(f.read_text()) if f.exists() else {}
    cands = []
    for pr in (items if items is not None else iter_prs(repo, kind)):
        ms = messages(pr)
        if pr["number"] and f"{repo}#{pr['number']}" not in done and score(ms) >= 3:
            cands.append((score(ms), pr, ms))
    cands = sorted(cands, key=lambda c: -c[0])[:limit]

    def one(c):
        _, pr, ms = c
        try:
            proposed = extract(client, model, pr, ms)
            kept, rej = verify(proposed, ms)
            n0 = len(kept)
            kept = judge(client, model, kept)
            rej += n0 - len(kept)
        except Exception as e:  # keep going; a failed PR is retried on the next run
            return None
        return f"{repo}#{pr['number']}", {"title": pr["title"], "url": pr["url"], "createdAt": ts(pr["createdAt"]),
                                          "decisions": kept, "rejected": rej}

    with ThreadPoolExecutor(workers) as ex:
        for i, res in enumerate(ex.map(one, cands)):
            if res:
                done[res[0]] = res[1]
            if i % 25 == 0:
                f.write_text(json.dumps(done)); print(repo, i, "/", len(cands), flush=True)
    f.write_text(json.dumps(done))
    kept = sum(len(v["decisions"]) for v in done.values()); rej = sum(v["rejected"] for v in done.values())
    print(f"{repo}: {len(done)} PRs, {kept} verified decisions, {rej} rejected (quote not in source)")


if __name__ == "__main__":
    kind = "issues" if sys.argv[1] == "--issues" else "prs"
    for repo in sys.argv[2 if kind == "issues" else 1:]:
        run(repo, kind=kind)
