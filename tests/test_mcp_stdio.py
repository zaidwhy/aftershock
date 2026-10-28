"""The MCP server, spoken to over stdio by a real MCP client, as Claude Desktop would."""
import asyncio
import json
import sys
from pathlib import Path

import pytest

pytest.importorskip("mcp")
from mcp import ClientSession, StdioServerParameters  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
TOOLS = {"artist_opportunities", "ask", "launch_brief", "launch_kit", "list_storms", "netflix_history", "ripple_score", "spillover_forecast", "sync_scout"}


async def _session_calls():
    params = StdioServerParameters(command=sys.executable, args=["-m", "aftershock.mcp_server"], cwd=str(ROOT))
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            names = {t.name for t in (await session.list_tools()).tools}
            asked = await session.call_tool("ask", {"question": "who will win the world cup"})
            return names, asked


def test_server_lists_every_tool_and_answers_a_question():
    names, asked = asyncio.run(_session_calls())
    assert names == TOOLS and len(names) == 9
    body = json.loads(asked.content[0].text)
    assert not asked.is_error and body["intent"] == "none" and "I can answer" in body["steps"][0]["note"] + str(body.get("answer"))
