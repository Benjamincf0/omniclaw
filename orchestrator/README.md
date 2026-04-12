# Omniclaw Orchestrator

A small orchestration service that sits between Discord and one or more MCP servers.

It does three things:

1. Receives a user message over HTTP.
2. Uses a selected model provider to decide whether MCP tools are needed.
3. Calls MCP tools, feeds the results back to the model, and returns the final reply.

## Why this exists

This is intentionally much smaller than OpenClaw. It keeps:

- In-memory conversation sessions
- MCP tool discovery and execution
- Provider-aware tool-calling for OpenAI, Ollama, Claude, and Gemini
- A single `/chat` endpoint for callers such as the Discord bot

It does not include:

- Multi-agent orchestration
- Persistence layers
- Web UI
- Workflow builders
- Complex plugin systems

## Environment

Required:

- `MODEL_PROVIDER` defaults to `openai`
- Default model settings for the selected provider:
  - `OPENAI_API_KEY` and `OPENAI_MODEL` for `MODEL_PROVIDER=openai`
  - `OLLAMA_MODEL` for `MODEL_PROVIDER=ollama`
  - `ANTHROPIC_API_KEY` and `ANTHROPIC_MODEL` for `MODEL_PROVIDER=claude`
  - `GEMINI_API_KEY` and `GEMINI_MODEL` for `MODEL_PROVIDER=gemini`

Optional:

- `OPENAI_BASE_URL` defaults to `https://api.openai.com/v1`
- `OLLAMA_BASE_URL` defaults to `http://127.0.0.1:11434/v1`
- `ANTHROPIC_BASE_URL` defaults to `https://api.anthropic.com`
- `GEMINI_BASE_URL` defaults to `https://generativelanguage.googleapis.com/v1beta`
- `MODEL_TEMPERATURE` defaults to `0.2`
- `MODEL_MAX_OUTPUT_TOKENS` defaults to `1024`
- Provider-specific `*_TEMPERATURE` and `*_MAX_OUTPUT_TOKENS` env vars override the shared defaults
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
  "provider": "gemini",
  "model": "gemini-2.5-pro",
  "message": "Do I have any unread MIOs?"
}
```

Response:

```json
{
  "session_id": "discord:guild:1:channel:2:user:3",
  "reply": "You have 3 recent MIOs...",
  "provider": "gemini",
  "model": "gemini-2.5-pro",
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

- `provider` and `model` are optional request fields. If omitted, the orchestrator uses the env-configured default provider and model.
- With a single MCP server, tool names are exposed as-is.
- With multiple MCP servers, tool names are automatically prefixed as `server__tool`.
- Session state is in memory only.
