"""Tool-calling agent. The model chooses tools and explains results; every fact comes from graph tool output."""
import inspect, json, time
from openai import OpenAI
from .config import env
from .db import QUERY_LOG
from . import mem
from .tools import TOOLS

SYSTEM = """You are Keystone, an engineering knowledge-risk agent over a graph built from public GitHub history.
Rules:
- Answer ONLY from tool results. Never invent people, PRs, dates or quotes. If a tool returns nothing or an error, say you do not know.
- Cite sources inline as [repo#number] for PRs. Quote decisions verbatim, in quotation marks, only from verbatim_quote fields.
- Knowledge risk is about modules, never a judgment of individuals. Never criticise or rank people negatively; only report evidence-supported facts.
- Plain text only, no markdown. Be concise: 3-6 sentences or a short list. Mention how you know (which signals) in one line.
Tools: who_knows (module/file expertise), suggest_reviewers (for a PR), bus_factor (modules with concentrated knowledge),
bridges (people connecting groups), connection (path between two people), why_decision (why something was decided, with sources),
recall_memory (this user's earlier questions and feedback; use when they refer to earlier conversation or to people they rejected/accepted).
If suggest_reviewers returns memory_notes, tell the user which rule changed the result."""

SPECS = [
 {"name": "recall_memory", "description": "Recall this user's earlier questions and accept/reject feedback about a topic, person, module or PR.",
  "parameters": {"type": "object", "properties": {"topic": {"type": "string"}}, "required": ["topic"]}},
 {"name": "who_knows", "description": "Who has the deepest recent knowledge of a module, directory, file path fragment, OR a free-text topic (e.g. 'variable-length traversal', 'docker packaging').",
  "parameters": {"type": "object", "properties": {"target": {"type": "string"}}, "required": ["target"]}},
 {"name": "suggest_reviewers", "description": "Suggest reviewers for a PR identified like 'FalkorDB/GraphRAG-SDK#328' (or just '328').",
  "parameters": {"type": "object", "properties": {"pr": {"type": "string"}}, "required": ["pr"]}},
 {"name": "bus_factor", "description": "Modules where knowledge is concentrated in one person with no active backup. Leave repo empty to cover all repos; only pass repo if the user names one exactly.",
  "parameters": {"type": "object", "properties": {"repo": {"type": "string"}}}},
 {"name": "bridges", "description": "People who connect otherwise separate groups of contributors (betweenness).",
  "parameters": {"type": "object", "properties": {}}},
 {"name": "connection", "description": "Shortest relationship path between two GitHub logins.",
  "parameters": {"type": "object", "properties": {"a": {"type": "string"}, "b": {"type": "string"}}, "required": ["a", "b"]}},
 {"name": "why_decision", "description": "Find past decisions (with verbatim quotes and source PRs) relevant to a question about why something was done.",
  "parameters": {"type": "object", "properties": {"question": {"type": "string"}}, "required": ["question"]}},
]
SPECS = [{"type": "function", "function": s} for s in SPECS]


def call_tool(tenant: str, name: str, args: dict, user: str | None = None):
    fn = TOOLS.get(name)
    if not fn:
        return {"data": {"error": f"unknown tool {name}"}, "evidence": {"nodes": [], "edges": []}, "cypher": ""}
    params = set(inspect.signature(fn).parameters)
    args = {k: v for k, v in args.items() if k in params - {"tenant", "user"} and isinstance(v, (str, int))}
    if "user" in params:
        args["user"] = user  # identity comes from the session, never from the model
    try:
        return fn(tenant, **args)
    except Exception as e:  # surface to the model rather than crash the request
        return {"data": {"error": f"{type(e).__name__}: {str(e)[:200]}"}, "evidence": {"nodes": [], "edges": []}, "cypher": name}


def ask(tenant: str, question: str, user: str | None = None, history: list[dict] | None = None, max_rounds: int = 4) -> dict:
    client, model = OpenAI(api_key=env("OPENAI_API_KEY")), env("OPENAI_MODEL", "gpt-4o-mini")
    msgs = [{"role": "system", "content": SYSTEM}, *(history or []), {"role": "user", "content": question}]
    trace, nodes, edges, structured = [], {}, [], {}
    for _ in range(max_rounds):
        r = client.chat.completions.create(model=model, messages=msgs, tools=SPECS, temperature=0)
        m = r.choices[0].message
        if not m.tool_calls:
            if user:
                mem.record_episode(user, question, m.content, [t["tool"] for t in trace], list(nodes))
            return {"answer": m.content, "trace": trace, "structured": structured,
                    "evidence": {"nodes": list(nodes.values()), "edges": edges}}
        msgs.append(m)
        for c in m.tool_calls:
            args = json.loads(c.function.arguments or "{}")
            log, tok = [], QUERY_LOG.set([])
            t = time.time()
            res = call_tool(tenant, c.function.name, args, user)
            structured[c.function.name] = res["data"]
            log = QUERY_LOG.get()
            QUERY_LOG.reset(tok)
            trace.append({"tool": c.function.name, "args": args, "ms": int((time.time() - t) * 1000), "queries": log})
            for n in res["evidence"]["nodes"]:
                nodes.setdefault(n["id"], n)
            edges += res["evidence"]["edges"]
            msgs.append({"role": "tool", "tool_call_id": c.id, "content": json.dumps(res["data"], ensure_ascii=False)[:6000]})
    return {"answer": "I could not complete that within the tool budget.", "trace": trace, "evidence": {"nodes": list(nodes.values()), "edges": edges}}
