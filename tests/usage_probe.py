"""Measures OpenAI usage of the real agent: runs the 14 routing questions and sums the token counts OpenAI reports.
    python tests/usage_probe.py        (needs OPENAI_API_KEY and a loaded FalkorDB; costs a few cents)
Writes data/usage_probe.json."""
import json, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import openai.resources.chat.completions as cc
import openai.resources.embeddings as ee

U = {"chat_calls": 0, "pin": 0, "pout": 0, "embed_calls": 0, "ein": 0}
_chat, _emb = cc.Completions.create, ee.Embeddings.create


def chat(self, *a, **k):
    r = _chat(self, *a, **k)
    U["chat_calls"] += 1; U["pin"] += r.usage.prompt_tokens; U["pout"] += r.usage.completion_tokens
    return r


def emb(self, *a, **k):
    r = _emb(self, *a, **k)
    U["embed_calls"] += 1; U["ein"] += r.usage.prompt_tokens
    return r


cc.Completions.create, ee.Embeddings.create = chat, emb
from keystone.agent import ask
from keystone.qa_eval import ROUTING

rows = []
for q, _ in ROUTING:
    before, t = dict(U), time.time()
    res = ask("falkordb", q)
    rows.append({**{k: U[k] - before[k] for k in U}, "q": q, "secs": round(time.time() - t, 1), "tool": (res.get("trace") or [{}])[0].get("tool")})
n = len(rows)
per = {k: round(sum(r[k] for r in rows) / n, 1) for k in U}
print(f"per question: {per['chat_calls']} chat calls, {per['pin']:.0f} prompt tokens, {per['pout']:.0f} completion tokens, {per['embed_calls']} embedding calls")
assert per["chat_calls"] <= 4, "agent used more rounds than expected"
(ROOT / "data").mkdir(exist_ok=True)
(ROOT / "data" / "usage_probe.json").write_text(json.dumps({"rows": rows, "per_question": per}))

from keystone.tracing import flush  # no-op unless OTEL_EXPORTER_OTLP_ENDPOINT is set
flush()
