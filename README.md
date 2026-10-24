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

## Auth0 OAuth (branch `feat/auth0-oauth-mcp`)

This branch **requires OAuth** for all Streamable HTTP MCP calls, including Langfuse observations and source-reader tools. Requests without a valid bearer token receive HTTP 401.

### Auth0 setup (one-time)

1. Create a free [Auth0 tenant](https://manage.auth0.com/). Note its domain, such as `example.us.auth0.com`.
2. Create an **API / Resource Server** with identifier matching your public MCP endpoint, e.g. `https://resolutive-keegan-humbler.ngrok-free.dev/mcp`. Set signing algorithm to **RS256**. Define permission/scope `mcp:read`. Ensure your user-facing OAuth application can request that scope; enable API RBAC and *Add Permissions in the Access Token* where appropriate.
3. Enable the **Resource Parameter Compatibility Profile** in Auth0 tenant advanced settings, so OAuth clients using RFC 8707's `resource` parameter can request tokens for this API. Without this, MCP clients might receive the wrong audience. See [Auth0 guidance](https://support.auth0.com/center/s/article/mcp-audience-error-with-auth0).
4. Configure a suitable **public OAuth client** supporting Authorization Code with PKCE and ChatGPT's supported client onboarding approach (pre-registered OAuth client / DCR / CIMD). Auth0-specific client registration and callback URL requirements need to be configured in Auth0, not in Docker. **The JWT verifier alone does not implement the login or client registration.** Confirm which registration method your ChatGPT workspace offers before trying to log in.
5. Create or choose an Auth0 user. Copy their Auth0 `user_id` (e.g. `auth0|abc123`) into the allowlist. This is the JWT `sub`, **not their email address**.

### Local configuration

Add to `.env`:

```dotenv
AUTH0_DOMAIN=example.us.auth0.com
AUTH0_AUDIENCE=https://resolutive-keegan-humbler.ngrok-free.dev/mcp
AUTH0_ALLOWED_SUBJECTS=auth0|your-auth0-user-id
```

The public MCP resource URL is derived from `NGROK_DOMAIN`. Use the **same value** as the Auth0 API identifier for `AUTH0_AUDIENCE`. Keep the ngrok domain and Auth0 audience stable. Start with:

```powershell
docker compose up -d --build
docker compose logs -f langfuse-mcp
```

### Validate protection

Without a token:

```powershell
curl.exe -i https://resolutive-keegan-humbler.ngrok-free.dev/mcp
```

Expected: **401 Unauthorized** with a `WWW-Authenticate` header. The MCP SDK publishes protected-resource discovery metadata at `/.well-known/oauth-protected-resource/mcp`. The tool calls are blocked at the HTTP layer.

With Auth0 configured in your ChatGPT client, authenticate and run `get_recent_observations` or `list_project_files`. A successful login requires correct Auth0 application/client registration and callbacks; this repository only implements the resource-server half.

Security: the MCP validates RS256 signatures against Auth0 JWKS, exact issuer/audience, expiration, `mcp:read` permission and the explicit subject allowlist. Do not disable protection for convenience, and never commit secrets to Git.

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

## Read local source code (optional project mount)

The Code Reader adds four read-only tools: `list_project_files`, `read_source_file`, `search_in_code`, and `get_project_structure`.

Set **SOURCE_CODE_PATH** in your local `.env` to the absolute directory of the specific project to inspect, for example:

```dotenv
SOURCE_CODE_PATH=D:/collectiviq.ai/my-backend
```

Use forward slashes on Windows. The source folder must exist. The mount uses `:ro` semantics and appears as `/workspace` in the MCP container. Files you edit are read immediately without rebuilding the image; the first mount change requires recreating the container:

```powershell
git switch feat/read-only-code-browser
docker compose up -d --build
docker compose exec langfuse-mcp ls /workspace
```

Open MCP Inspector or refresh the ChatGPT MCP plugin tool list, then ask: "List the project files" or "Read the first 100 lines of main.py". Paths given to the tools are **relative** to the mounted source directory.

Restrictions: supported source extensions only; hidden files and directories, `.env*`, `.git`, `node_modules`, typical build folders, and credentials directories are excluded. Path traversal, absolute paths, and symbolic links are rejected. Individual files are limited to 128 KiB; listings scan at most 1000 candidate files; responses and searches are bounded. Treat this as a defense-in-depth filter, **not** a substitute for strong MCP authentication or a carefully scoped mount. Never mount an entire home directory or a folder containing secrets.

**Critical:** ngrok currently exposes this MCP publicly without inbound authorization. Do not enable source browsing with proprietary code or sensitive documents until an authentication/access-control layer compatible with your MCP client has been added.

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
