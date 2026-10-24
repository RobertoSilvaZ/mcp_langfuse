"""Read-only Langfuse MCP server. Input/output are returned unredacted by design.

WARNING: Traces may contain personal data, secrets or proprietary prompts.
The MCP HTTP listener should be accessible only to trusted clients.
"""
import os
from datetime import datetime, timedelta, timezone

import httpx
from mcp.server import MCPServer
from mcp.server.auth.settings import AuthSettings
from pydantic import AnyHttpUrl
from auth0_verifier import Auth0TokenVerifier, ISSUER
from code_reader import (list_project_files as _list_files, read_source_file as _read_file,
                         search_in_code as _search_code, get_project_structure as _structure)

PUBLIC_URL = os.environ["MCP_PUBLIC_URL"].rstrip("/")
if not PUBLIC_URL.startswith("https://"):
    raise ValueError("MCP_PUBLIC_URL must be https://...")
mcp = MCPServer(
    "Langfuse MCP",
    token_verifier=Auth0TokenVerifier(),
    auth=AuthSettings(
        issuer_url=AnyHttpUrl(ISSUER),
        resource_server_url=AnyHttpUrl(PUBLIC_URL),
        required_scopes=["mcp:read"],
        validate_token_resource=False,  # Auth0 uses its own API audience, checked in verifier.
    ),
)
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
        if response.status_code == 404:
            endpoint = f"{HOST}{OBS_PATH}"
            if API_VERSION == "v2":
                raise ValueError(
                    f"Langfuse endpoint not found: {endpoint}. "
                    "Observations API v2 requires Langfuse v4+. "
                    "If using self-hosted Langfuse v3, set LANGFUSE_API_VERSION=v1 "
                    "in .env and recreate the container. Otherwise verify LANGFUSE_HOST."
                )
            raise ValueError(
                f"Langfuse endpoint not found: {endpoint}. "
                "Verify LANGFUSE_HOST and reverse-proxy routing."
            )
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


@mcp.tool()
def list_project_files(limit: int = 200) -> dict:
    """List permitted files in the mounted read-only source directory."""
    return _list_files(limit)


@mcp.tool()
def read_source_file(path: str, start_line: int = 1, max_lines: int = 200) -> dict:
    """Read numbered source lines from a permitted file."""
    return _read_file(path, start_line, max_lines)


@mcp.tool()
def search_in_code(query: str, limit: int = 30) -> dict:
    """Search permitted code and Markdown files for a literal string."""
    return _search_code(query, limit)


@mcp.tool()
def get_project_structure(limit: int = 200) -> dict:
    """Display source-file structure of the mounted project."""
    return _structure(limit)


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8787)
