# Langfuse MCP (Docker Compose)

Read-only MCP server for self-hosted Langfuse, exposing observation **input and output by default**. The ngrok service starts automatically alongside the MCP server.

## Setup

```powershell
Copy-Item .env.example .env
# Edit .env with the actual Langfuse API keys, host, and ngrok authtoken
docker compose up -d --build
docker compose logs -f ngrok
```

The local endpoint is `http://localhost:8787/mcp`. The remote endpoint uses the reserved domain from `NGROK_DOMAIN`, e.g. `https://resolutive-keegan-humbler.ngrok-free.dev/mcp`.

The ngrok container reaches `http://langfuse-mcp:8787` over the private Compose network; no Windows ngrok executable is needed. Ensure no other ngrok session is using the same reserved domain.

To stop both services: `docker compose down`.

### Configuration

- `LANGFUSE_HOST`: Langfuse URL accessible *inside* the MCP container. For Langfuse on Windows port 8099, use `http://host.docker.internal:8099`.
- `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY`: Langfuse project keys.
- `LANGFUSE_API_VERSION`: `v1` for Langfuse v3, `v2` for v4+.
- `NGROK_DOMAIN`: reserved ngrok domain, **without** protocol or path.
- `NGROK_AUTHTOKEN`: ngrok account authtoken; never commit it.

## Connect to ChatGPT

After `docker compose up -d --build` is running and ngrok has started:

1. Open [ChatGPT Plugins](https://chatgpt.com/plugins) in the ChatGPT account where you want to use the MCP server.
2. Select **+** and choose **Add custom MCP server** (wording/availability may depend on your ChatGPT account and workspace).
3. Name the connection **Langfuse Local**.
4. Select the option to connect to a remote MCP server by **URL**, and paste:
   `https://resolutive-keegan-humbler.ngrok-free.dev/mcp`
   If using a different reserved domain, use `https://<NGROK_DOMAIN>/mcp` instead.
5. Complete the plugin's connection flow and select it in a conversation.
6. Test: ask **"List the available Langfuse Local tools"**, then **"Retrieve my 3 most recent Langfuse observations, including input and output"**.

If the plugin reports a connection error, verify the ngrok container is running with `docker compose logs --tail=50 ngrok`, then connect with [MCP Inspector](https://github.com/modelcontextprotocol/inspector) using the exact same HTTPS URL and **Streamable HTTP**.

**Security:** A successful connection is not proof the public endpoint is safe. This MCP currently lacks inbound authentication and exposes full trace I/O. Restrict to test data until compatible authentication/access controls are added. Never paste ngrok or Langfuse credentials into ChatGPT.

### MCP Tools

- `get_recent_observations(hours, limit, cursor)` — observations with complete input/output.
- `get_errors(hours, limit)` — error observations with complete input/output.
- `get_trace_observations(trace_id, hours, limit, cursor)` — trace observations with complete input/output.

For Langfuse v4+, `/api/public/v2/observations` uses the `io` field group. Langfuse v3 uses `/api/public/observations`.

### Security — read before enabling ngrok

**The ngrok domain is publicly reachable. This MCP server currently has no inbound authentication and returns unredacted prompts, responses, and metadata. Anyone able to access the endpoint may invoke its tools.** This automatic ngrok service should only be used with synthetic/test data until MCP-compatible authentication (for example OAuth with access controls) is implemented. An ngrok authtoken only authenticates ngrok's tunnel agent; **it does not protect the public MCP endpoint**.

`.env` is gitignored. Avoid committing API credentials.

### References

- https://langfuse.com/docs/api-and-data-platform/features/observations-api
- https://ngrok.com/docs/using-ngrok-with/docker/
