"""Start the MCP server over stdio and call it like a real MCP client would."""
import asyncio, json, sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    params = StdioServerParameters(command=sys.executable, args=["-m", "keystone.mcp_server"])
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            tools = await s.list_tools()
            print("tools:", [t.name for t in tools.tools])
            res = await s.call_tool("who_knows", {"target": "variable-length traversal"})
            print(res.content[0].text[:300])
            res = await s.call_tool("bus_factor", {})
            print(res.content[0].text[:200])


asyncio.run(main())
