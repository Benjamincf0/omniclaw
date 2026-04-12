# Omniclaw TUI

A terminal chat client for the Omniclaw orchestrator.

## Run

```bash
uv run omniclaw-tui
```

The client talks to the same orchestrator HTTP API used by the Discord bot:

- `ORCHESTRATOR_URL` defaults to `http://127.0.0.1:8080`
- `TUI_SESSION_ID` optionally pins the chat session
- `TUI_USER_ID` defaults to your local login name
- `TUI_USER_NAME` defaults to your local login name
- `TUI_PROVIDER` optionally overrides the orchestrator provider
- `TUI_MODEL` optionally overrides the orchestrator model
- `TUI_HTTP_TIMEOUT_SECONDS` defaults to `90`

## Keys

- `Enter` sends the current prompt
- `Ctrl+C` quits

## Commands

- `/help` shows the command list inside the TUI
- `/status` checks the orchestrator health endpoint
- `/reset` clears the current remote session
- `/provider <name>` sets a provider override for future messages
- `/model <name>` sets a model override for future messages
- `/provider default` and `/model default` clear overrides
- `/session new` starts a fresh local session id
- `/quit` exits the app
