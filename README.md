# Omniclaw

Your personal omnivox assistant. Integrate with OpenClaw, Claude Code, Codex, or use the web client to ask and do anything on omnivox for you.

## New lightweight Discord architecture

This repo now includes a smaller client/server integration path in addition to the standalone `mcp-server`.

- [`mcp-server`](/Users/vincentliu/dev/tui/mcp-server): the existing Omnivox MCP server
- [`orchestrator`](/Users/vincentliu/dev/tui/orchestrator): a lightweight AI orchestration service that talks to one or more MCP servers
- [`discord-bot`](/Users/vincentliu/dev/tui/discord-bot): a thin Discord client that forwards messages to the orchestrator
- [`tui-client`](/Users/vincentliu/dev/tui/tui-client): a terminal UI client that talks to the same orchestrator API

The intended request flow is:

1. A user sends a message from Discord or the TUI.
2. The client forwards it to the orchestrator.
3. The orchestrator decides whether to call MCP tools.
4. The orchestrator returns a final reply to the client.
5. The client renders that reply back to the user.

## Quick start

There are two ways to run OmniClaw depending on whether you want to use the pre-built binaries or run from the source code.

#### Option 1: Desktop Installation (Recommended)

Download the latest version for your operating system from the [`Releases`](https://github.com/Benjamincf0/omniclaw/releases) page.

    Windows: Run the .exe installer.
    macOS: Open the .pkg file to install.
    
    Note: As the app is currently unsigned, you may see a security warning. On Windows, click "More Info" -> "Run Anyway." On macOS, right-click the file and select "Open."

#### Option 2: Run from source:

```bash
cp .env.example .env
./omniclaw up
```
or for Windows users
```cmd
python ./omniclaw up
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
./omniclaw tui
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

  ## 🎥 Demo
[![Demo](https://img.youtube.com/vi/bILXbqu0I_Q/0.jpg)](https://youtu.be/bILXbqu0I_Q)
