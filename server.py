"""Read-only Langfuse MCP server. Input/output are returned unredacted by design.

WARNING: Traces may contain personal data, secrets or proprietary prompts.
The MCP HTTP listener should be accessible only to trusted clients.
"""
import os
from datetime import datetime, timedelta, timezone

import httpx
from mcp.server import MCPServer

mcp = MCPServer("Langfuse MCP")
HOST = os.environ["LANGFUSE_HOST"].rstrip("/")
PUBLIC_KEY = os.environ["LANGFUSE_PUBLIC_KEY"]
SECRET_KEY = os.environ["LANGFUSE_SECRET_KEY"]
API_VERSION = os.getenv("LANGFUSE_API_VERSION", "v2").lower()

if API_VERSION not in ("v1", "v2"):
    raise ValueError("LANGFUSE_API_VERSION must be v1 or v2")

# 'io' is essential: without it, v2 silently omits input and output.
FIELDS = "core,basic,time,io,metadata,model,usage,prompt,metrics,trace_context"
OBS_PATH = "/api/public/v2/observations" if API_VERSION == "v2" else "/api/public/observations"


async def query_observations(params: dict) -> dict:
    if API_VERSION == "v2":
        params = {**params, "fields": FIELDS}
    else:
        params.pop("cursor", None)
    async with httpx.AsyncClient(auth=(PUBLIC_KEY, SECRET_KEY), timeout=30) as client:
        response = await client.get(f"{HOST}{OBS_PATH}", params=params)
        response.raise_for_status()
        return response.json()


def bounded_range(hours: int) -> dict:
    now = datetime.now(timezone.utc)
    start = now - timedelta(hours=max(1, min(hours, 168)))
    return {
        "fromStartTime": start.isoformat(),
        "toStartTime": now.isoformat(),
    }


@mcp.tool()
async def get_recent_observations(hours: int = 24, limit: int = 50, cursor: str = "") -> dict:
    """Read recent Langfuse observations with COMPLETE input/output, metadata,
    token usage and model info. Input/output may contain sensitive information.
    Use the returned meta.cursor to fetch the next page on Langfuse v4."""
    params = {**bounded_range(hours), "limit": max(1, min(limit, 100))}
    if cursor and API_VERSION == "v2":
        params["cursor"] = cursor
    return await query_observations(params)


@mcp.tool()
async def get_errors(hours: int = 24, limit: int = 50) -> dict:
    """Read ERROR-level Langfuse observations, including full input/output."""
    return await query_observations({
        **bounded_range(hours),
        "limit": max(1, min(limit, 100)),
        "level": "ERROR",
    })


@mcp.tool()
async def get_trace_observations(trace_id: str, hours: int = 168, limit: int = 100, cursor: str = "") -> dict:
    """Read a trace's observations including full prompts (input) and responses (output).

    The hours window is required to bound queries on v4; increase it up to 168
    for older traces. The v4 response may include meta.cursor for pagination.
    """
    if not trace_id.strip():
        raise ValueError("trace_id is required")
    params = {
        **bounded_range(hours),
        "traceId": trace_id.strip(),
        "limit": max(1, min(limit, 100)),
    }
    if cursor and API_VERSION == "v2":
        params["cursor"] = cursor
    return await query_observations(params)


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8787)
