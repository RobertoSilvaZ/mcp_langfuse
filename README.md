# Langfuse MCP (Docker Compose)

Read-only MCP server for self-hosted Langfuse, exposing observation **input and output by default**, alongside timestamps, model, usage, metadata, and errors. **Raw prompts and responses may contain PII, credentials, and other sensitive data. Use only with trusted MCP clients.**

## Quick start

```bash
cp .env.example .env
# Edit .env with the project's Langfuse public/secret API keys and host
# v4+ -> LANGFUSE_API_VERSION=v2, v3 -> v1
docker compose up -d --build
docker compose logs -f langfuse-mcp
```

The MCP endpoint is `http://localhost:8787/mcp` on the Docker host. Use MCP Inspector or a private tunnel to connect a compatible MCP client. **Do not expose port 8787 directly to the public Internet:** it has no inbound authentication and returns full trace I/O.

By default, the container reaches Langfuse at `http://host.docker.internal:3000`. If Langfuse only listens on a Docker-internal network, attach this container to that network and change `LANGFUSE_HOST` to the actual Langfuse service hostname, e.g. `http://langfuse-web:3000`.

## Tools

- `get_recent_observations(hours, limit, cursor)` — recent observations and full input/output.
- `get_errors(hours, limit)` — ERROR-level observations and full input/output.
- `get_trace_observations(trace_id, hours, limit, cursor)` — observations for a trace with full input/output.

### Compatibility

- **Langfuse v4+**: `/api/public/v2/observations` with `fields=core,basic,time,io,metadata,model,usage,prompt,metrics,trace_context`. The `io` field group explicitly includes `input` and `output`. Responses from this version return raw strings for I/O; consumers may parse JSON when appropriate. v2 supports `meta.cursor` pagination.
- **Self-hosted Langfuse v3**: legacy `/api/public/observations` returns complete observation records. API pagination differs; cursor is not supported.

Time-window parameters are deliberately bounded to the most recent seven days. Add filtering/pagination for older trace history as needed.

## Security

- `.env` is gitignored. Never commit Langfuse API keys.
- This server **does not redact** observation inputs or outputs; treat the connection as privileged access.
- Port binding `127.0.0.1:8787:8787` restricts exposure to the Docker host.
- For remote ChatGPT access, use an authenticated/private tunnel and appropriate access controls; verify your ChatGPT plan supports custom MCP connections.

## References

- https://langfuse.com/docs/api-and-data-platform/features/observations-api
- https://py.sdk.modelcontextprotocol.io/run/
