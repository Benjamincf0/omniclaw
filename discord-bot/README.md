# Omniclaw Discord Bot

A thin Discord client for the Omniclaw orchestrator.

The bot does not talk to MCP servers directly. It forwards Discord messages to the orchestration service, then sends the orchestration reply back to Discord.

## Environment

Required:

- `DISCORD_BOT_TOKEN`

Optional:

- `ORCHESTRATOR_URL` defaults to `http://127.0.0.1:8080`
- `DISCORD_REQUIRE_MENTION` defaults to `true`
- `DISCORD_ALLOW_DMS` defaults to `true`
- `DISCORD_CHANNEL_IDS` comma-separated channel ids where the bot should reply without a mention
- `DISCORD_REPLY_CHAR_LIMIT` defaults to `1900`
- `DISCORD_HTTP_TIMEOUT_SECONDS` defaults to `90`

## Run

```bash
uv sync
uv run omniclaw-discord-bot
```

## Behavior

- Ignores other bots
- Replies in DMs by default
- In servers, replies when mentioned
- Can also reply automatically in configured channels without slash commands or prefixed commands
- Uses one conversation session per `guild/channel/user` combination
