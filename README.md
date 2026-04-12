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
