# Omniclaw

Your personal omnivox assistant. Integrate with OpenClaw, Claude Code, Codex, or use the web client to ask and do anything on omnivox for you.

## New lightweight Discord architecture

This repo now includes a smaller Discord-first integration path in addition to the standalone `mcp-server`.

- [`mcp-server`](/Users/vincentliu/dev/omniclaw/mcp-server): the existing Omnivox MCP server
- [`orchestrator`](/Users/vincentliu/dev/omniclaw/orchestrator): a lightweight AI orchestration service that talks to one or more MCP servers
- [`discord-bot`](/Users/vincentliu/dev/omniclaw/discord-bot): a thin Discord client that forwards messages to the orchestrator

The intended request flow is:

1. A Discord user sends a normal message.
2. The Discord bot forwards it to the orchestrator.
3. The orchestrator decides whether to call MCP tools.
4. The orchestrator returns a final reply to the bot.
5. The bot posts that reply back to Discord.

## Quick start

The easiest way to run the full stack on one server is from the repo root:

```bash
cp .env.example .env
./omniclaw up
```

That command will:

1. Load the shared root `.env`
2. Run `uv sync` for `mcp-server`, `orchestrator`, and `discord-bot`
3. Start all three services together with prefixed logs
4. Stop the whole stack cleanly on `Ctrl+C`

Required environment variables for the combined stack:

- `MODEL_PROVIDER`
- Provider-specific default model credentials:
  - `OPENAI_API_KEY` + `OPENAI_MODEL` for `MODEL_PROVIDER=openai`
  - `OLLAMA_MODEL` for `MODEL_PROVIDER=ollama`
  - `ANTHROPIC_API_KEY` + `ANTHROPIC_MODEL` for `MODEL_PROVIDER=claude`
  - `GEMINI_API_KEY` + `GEMINI_MODEL` for `MODEL_PROVIDER=gemini`
- `DISCORD_BOT_TOKEN`

Helpful helper commands:

```bash
./omniclaw sync
./omniclaw env
./omniclaw up --no-sync
```

Each folder still has its own `README.md` if you want to run a single service by itself.

```
 ┌─────────────────────────────────────────────────────────────────┐
  │                         USER BROWSER                            │
  │                      (frontend/src/)                            │
  │                     React + Vite App                            │
  └────────────────────────┬────────────────────────────────────────┘
                           │ POST /chat
                           │ { message, history }
                           ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │                     ORCHESTRATOR :8080                          │
  │              omniclaw_orchestrator/server.py                    │
  │                      FastAPI + CORS                             │
  │                                                                 │
  │   load_config()  ←  MODEL_PROVIDER env var                      │
  │        │                                                        │
  │        ▼                                                        │
  │   ModelClientRegistry                                           │
  │        │                                                        │
  │        ├── MODEL_PROVIDER=gemini  →  GeminiChatClient           │
  │        ├── MODEL_PROVIDER=ollama  →  OpenAICompatibleClient     │
  │        ├── MODEL_PROVIDER=openai  →  OpenAICompatibleClient     │
  │        └── MODEL_PROVIDER=claude  →  AnthropicChatClient        │
  │                                                                 │
  │   MultiServerMcpClient  (fetches & calls MCP tools)            │
  └──────────┬──────────────────────────┬───────────────────────────┘
             │ MCP over HTTP            │ HTTPS API calls
             │ streamable-http          │
             ▼                          ▼
  ┌─────────────────────┐   ┌──────────────────────────────────────┐
  │   MCP SERVER :8000  │   │           LLM PROVIDERS              │
  │   omni.py           │   │                                      │
  │   FastMCP + FastAPI │   │  ┌─────────────────────────────┐     │
  │                     │   │  │  Gemini API (cloud)          │     │
  │  Tools exposed:     │   │  │  generativelanguage.google   │     │
  │  • get_mio          │   │  │  GEMINI_API_KEY required     │     │
  │  • get_mio_item     │   │  └─────────────────────────────┘     │
  │  • send_mio         │   │                                      │
  │  • get_news         │   │  ┌─────────────────────────────┐     │
  │  • get_news_item    │   │  │  Ollama (local)              │     │
  │                     │   │  │  localhost:11434             │     │
  └──────────┬──────────┘   │  │  no API key needed           │     │
             │              │  └─────────────────────────────┘     │
             │ HTTPS        └──────────────────────────────────────┘
             ▼
  ┌─────────────────────────────────────────────────────────────────┐
  │               OMNIVOX  (johnabbott.omnivox.ca)                  │
  │                  Cookie-based auth session                       │
  │              /mio  /news  endpoints (scraped HTML)              │
  └─────────────────────────────────────────────────────────────────┘

                           DISCORD BOT
  ┌─────────────────────────────────────────────────────────────────┐
  │                    discord-bot/ :separate                        │
  │              Connects to Discord Gateway API                     │
  │              POST /chat  →  Orchestrator :8080                  │
  └─────────────────────────────────────────────────────────────────┘

  Request flow for a chat message:

  1. Browser sends POST /chat to Orchestrator :8080
  2. Orchestrator picks the LLM based on MODEL_PROVIDER
  3. LLM responds — if it wants data, it returns a tool call
  4. Orchestrator calls the MCP Server :8000 with the tool name + args
  5. MCP Server scrapes Omnivox and returns the data
  6. Orchestrator feeds the result back to the LLM
  7. LLM produces a final reply → returned to the browser
  ```
