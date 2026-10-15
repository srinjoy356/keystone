"""Keystone as an MCP server: any MCP client (Claude Desktop, Cursor, ...) can pick among the same read-only graph tools.
Run:  python -m keystone.mcp_server        (stdio).  Tenant via KEYSTONE_TENANT (default falkordb)."""
from mcp.server.mcpserver import MCPServer
from . import tools
from .config import env

mcp = MCPServer("keystone")
TENANT = env("KEYSTONE_TENANT", "falkordb")


def _run(name: str, **kw):
    r = tools.TOOLS[name](TENANT, **kw)
    return {"result": r["data"], "evidence_nodes": len(r["evidence"]["nodes"]), "query": r["cypher"]}


@mcp.tool()
def who_knows(target: str) -> dict:
    """Who has the deepest recent knowledge of a module/path or a free-text topic (e.g. 'variable-length traversal')."""
    return _run("who_knows", target=target)


@mcp.tool()
def suggest_reviewers(pr: str) -> dict:
    """Suggest reviewers for a PR like 'FalkorDB/GraphRAG-SDK#328', with the earlier PRs that justify each suggestion."""
    return _run("suggest_reviewers", pr=pr)


@mcp.tool()
def bus_factor(repo: str | None = None) -> dict:
    """Modules where knowledge is concentrated in one person with no active backup (module-level, not a judgment of people)."""
    return _run("bus_factor", repo=repo)


@mcp.tool()
def bridges() -> dict:
    """People who connect otherwise separate groups of contributors (betweenness centrality)."""
    return _run("bridges")


@mcp.tool()
def connection(a: str, b: str) -> dict:
    """Shortest relationship path between two GitHub logins."""
    return _run("connection", a=a, b=b)


@mcp.tool()
def why_decision(question: str) -> dict:
    """Past decisions relevant to a question, with verbatim quotes and links to the source PR or issue."""
    return _run("why_decision", question=question)


if __name__ == "__main__":
    mcp.run()
