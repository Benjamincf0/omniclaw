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

1. Start the Omnivox MCP server from [`mcp-server`](/Users/vincentliu/dev/omniclaw/mcp-server).
2. Start the orchestrator from [`orchestrator`](/Users/vincentliu/dev/omniclaw/orchestrator).
3. Start the bot from [`discord-bot`](/Users/vincentliu/dev/omniclaw/discord-bot).

Each folder has its own `README.md` with its required environment variables.
