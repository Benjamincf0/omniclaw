# Omniclaw Orchestrator

A small orchestration service that sits between Discord and one or more MCP servers.

It does three things:

1. Receives a user message over HTTP.
2. Uses an OpenAI-compatible chat-completions model to decide whether MCP tools are needed.
3. Calls MCP tools, feeds the results back to the model, and returns the final reply.

## Why this exists

This is intentionally much smaller than OpenClaw. It keeps:

- In-memory conversation sessions
- MCP tool discovery and execution
- An OpenAI-compatible tool-calling loop
- A single `/chat` endpoint for callers such as the Discord bot

It does not include:

- Multi-agent orchestration
- Persistence layers
- Web UI
- Workflow builders
- Complex plugin systems

## Environment

Required:

- `OPENAI_API_KEY`
- `OPENAI_MODEL`

Optional:

- `OPENAI_BASE_URL` defaults to `https://api.openai.com/v1`
- `ORCHESTRATOR_HOST` defaults to `127.0.0.1`
- `ORCHESTRATOR_PORT` defaults to `8080`
- `MCP_SERVER_URLS` defaults to `omnivox=http://127.0.0.1:8000/mcp`
- `MCP_SERVER_AUTH_TOKENS` format: `name=token,name2=token2`
- `ORCHESTRATOR_HISTORY_LIMIT` defaults to `24`
- `ORCHESTRATOR_MAX_TOOL_ROUNDS` defaults to `8`

## Run

```bash
uv sync
uv run omniclaw-orchestrator
```

## API

`POST /chat`

```json
{
  "session_id": "discord:guild:1:channel:2:user:3",
  "user_id": "3",
  "user_name": "Vincent",
  "message": "Do I have any unread MIOs?"
}
```

Response:

```json
{
  "session_id": "discord:guild:1:channel:2:user:3",
  "reply": "You have 3 recent MIOs...",
  "tool_calls": [
    {
      "name": "get_mio",
      "arguments": {
        "num": 10
      }
    }
  ]
}
```

## Notes

- With a single MCP server, tool names are exposed as-is.
- With multiple MCP servers, tool names are automatically prefixed as `server__tool`.
- Session state is in memory only.
