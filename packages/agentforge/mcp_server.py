"""Private stdio MCP server. Credentials and tenant never enter model-controlled arguments."""

import os
from mcp.server.fastmcp import FastMCP
from .sandbox import observe, execute

mcp = FastMCP("AgentForge sandbox tools")


@mcp.tool()
def inspect_scenario(scenario: str) -> dict:
    if scenario not in ("incident", "sdlc", "knowledge", "workflow", "reliability"):
        raise ValueError("Unknown scenario")
    return observe(scenario)


@mcp.tool()
def apply_approved_action(action: str) -> dict:
    return execute(os.environ["AGENTFORGE_DB"], os.environ["TOOL_TENANT"], os.environ["TOOL_RUN_ID"], action)


if __name__ == "__main__":
    mcp.run(transport="stdio")
