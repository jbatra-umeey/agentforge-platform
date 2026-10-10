import asyncio
import json
import os
import sys
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class ToolClient:
    def __init__(self, store):
        self.store = store

    async def call(self, tenant, run_id, name, arguments):
        if name not in ("inspect_scenario", "apply_approved_action"):
            raise PermissionError("Tool is not allowlisted")
        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "PYTHONPATH": str(Path(__file__).resolve().parents[1]),
            "AGENTFORGE_DB": self.store.path,
            "TOOL_TENANT": tenant,
            "TOOL_RUN_ID": run_id,
        }
        params = StdioServerParameters(command=sys.executable, args=["-m", "agentforge.mcp_server"], env=env)
        async with asyncio.timeout(30):
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(name, arguments)
                    if result.isError:
                        raise RuntimeError("MCP tool rejected the operation")
                    for block in result.content:
                        if block.type == "text":
                            return json.loads(block.text)
        raise RuntimeError("Tool returned no JSON result")
