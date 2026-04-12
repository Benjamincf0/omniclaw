# AGENTS.md

This repo contains **Omniclaw** — a John Abbott College Omnivox assistant consisting of:
- `mcp-server/` — Python FastMCP backend (MCP tools + HTTP endpoints via `@mcp.custom_route()`)
- `frontend/` — React/Vite chat UI

## Project Context

Omnivox has no public API. Omniclaw captures a student's Omnivox session cookies via Playwright browser automation and replays them on subsequent httpx HTTP requests to scrape Omnivox pages. Cookies are stored per-user in `user_tokens.json`, keyed by the student's Auth0 `sub` claim.

---

## Commands

### Python backend (`mcp-server/`)

All Python commands use `uv`. Always run from the `mcp-server/` directory.

| Task | Command |
|---|---|
| Install dependencies | `uv sync` |
| Start server | `uv run omni.py` |
| Run news integration test | `uv run python test_news.py` |
| Run server smoke test | `uv run python test_server.py` |
| Run a single test file | `uv run python <test_file>.py` |

There is no pytest setup. Test files use `asyncio.run(main())` as their entry point and print results to stdout. A non-zero `sys.exit` indicates failure.

### Frontend (`frontend/`)

Supports both `npm` and `bun` (a `bun.lock` is present alongside `package-lock.json`).

| Task | Command |
|---|---|
| Install dependencies | `npm install` or `bun install` |
| Start dev server | `npm run dev` or `bun run dev` |
| Build for production | `npm run build` |
| Lint | `npm run lint` |
| Preview production build | `npm run preview` |

There are no frontend tests configured.

---

## Architecture

```
omniclaw/
├── mcp-server/
│   ├── omni.py            # Main server: FastMCP tools + custom HTTP routes
│   ├── omnivox_client.py  # Authenticated httpx client (per-user + legacy)
│   ├── auth_manager.py    # Playwright login: headed + headless flows
│   ├── user_store.py      # JSON file store: Auth0 sub → Omnivox cookie string
│   ├── models/
│   │   ├── news.py        # Pydantic models + BeautifulSoup news scraping
│   │   ├── mio.py         # Pydantic models + BeautifulSoup MIO scraping
│   │   ├── lea_classes.py # Pydantic models + LEA class dashboard scraping
│   │   └── lea_details.py # Pydantic models + LEA detail page scraping
│   ├── user_tokens.json   # Runtime: per-user Omnivox cookies (gitignored)
│   ├── auth.txt           # Runtime: legacy single-user cookie (gitignored)
│   └── .env               # Secrets (gitignored)
└── frontend/
    └── src/
        ├── main.jsx       # Entry point: Auth0Provider + App
        ├── App.jsx        # Router: /auth → /setup|/link-omnivox → / (chat)
        └── components/    # AuthPage, SetupPage, Header, Message, ChatInput,
                           # QuickChips, WelcomeScreen, TypingIndicator,
                           # Sidebar, HowToUse, GlancePanel, ConsentScreen,
                           # SettingsModal
```

### Key runtime behavior
- `mcp.run(transport="http", ...)` starts a single uvicorn server on port 8000 serving both the MCP protocol and all custom HTTP routes. There is no separate FastAPI app.
- HTTP endpoints are registered with `@mcp.custom_route()`. Handlers receive a Starlette `Request` and return a Starlette `Response`. They do not use FastAPI dependency injection or `HTTPException`.
- CORS is applied via the `middleware` parameter on `mcp.run()`.
- The `/chat` endpoint proxies messages to Gemini (`gemini-2.5-flash`) with an agentic tool-call loop and conversation history.
- Gemini retries up to 3 times with exponential backoff on `429 / RESOURCE_EXHAUSTED`.

### Omnivox login flow (two-phase with 2FA support)
`POST /setup-omnivox` returns `{session_id}` immediately and spawns an `asyncio.Task` running `authenticate_headless`. The frontend polls `GET /setup-status?session_id=<id>` every 1.5 s. If Omnivox shows a 2FA verification page, the task pauses on an `asyncio.Event` and the session status becomes `"needs_otp"`. The frontend shows a code input; on submit it calls `POST /setup-2fa` which sets the code and fires the event, resuming Playwright. The session eventually reaches `"success"` or `"error"`, which the poll detects and cleans up.

2FA detection relies on `_OTP_INPUT_SELECTOR` in `auth_manager.py` — verify this against the actual Omnivox 2FA page HTML if the selector needs updating.

---

## Python Code Style

### Imports
Order: stdlib → third-party → local. Use `from __future__ import annotations` in modules with forward references (e.g. `models/news.py`).

```python
import asyncio
import os

import httpx
from starlette.requests import Request
from starlette.responses import JSONResponse

from models.news import AllNewsReq, AllNewsRes
from omnivox_client import omnivox_request_for_user
```

### Naming
- `snake_case` for functions, variables, and module-level constants that are internal.
- `SCREAMING_SNAKE_CASE` for true constants (`SYSTEM_PROMPT`, `FRONTEND_URL`, etc.).
- `PascalCase` for all classes, especially Pydantic models (`AllNewsRes`, `MioRes`).
- Prefix private helpers with `_` (`_build_headers`, `_is_auth_failure`, `_normalize_text`).

### Types
- Add type hints to all function signatures.
- Use modern union syntax: `str | None`, not `Optional[str]`.
- Use lowercase generics: `list[str]`, `dict[str, str]` (Python 3.10+).
- Pydantic `BaseModel` subclasses for all MCP tool input/output shapes.

### Async
- All functions that touch Omnivox or external APIs must be `async def`.
- Use `asyncio.sleep` for backoff; never use blocking `time.sleep` in async code.

### Error handling
- Raise semantically appropriate exceptions: `ValueError` for bad input/config, `RuntimeError` for auth failures, `PermissionError` after all retries exhausted.
- In `@mcp.custom_route()` handlers, return `JSONResponse({"detail": "..."}, status_code=4xx)` directly — do not raise `HTTPException`.
- Use `429` / `502` status codes for Gemini rate-limit vs. other upstream errors.
- Retry pattern: `for attempt in range(3)` with `asyncio.sleep(2**attempt)`.

### Docstrings
- Short one-line docstrings on all public functions and `@mcp.tool()` handlers. These docstrings become the tool descriptions visible to AI clients — keep them accurate.

---

## JavaScript/JSX Code Style

### Language
Plain JavaScript + JSX. No TypeScript. No PropTypes. `@types/react` is present for editor inference only.

### Imports
- React hooks from `"react"` first.
- Third-party packages next (`framer-motion`, `react-markdown`, `lucide-react`).
- Local components last, as default imports (no file extensions inside `src/`).

```jsx
import { useState, useRef, useEffect } from "react"
import { motion } from "framer-motion"
import Header from "./components/Header"
```

### Naming
- `PascalCase` for component names and their files (`ChatInput.jsx`, `WelcomeScreen.jsx`).
- `camelCase` for functions, variables, and props.
- `SCREAMING_SNAKE_CASE` for module-level constants (`BACKEND_URL`).

### Components
- All components are functional with a default export.
- Props are destructured directly in the function signature: `function ChatInput({ onSend, disabled })`.
- No class components.

### State & effects
- Use `useState`, `useRef`, `useEffect` from React.
- No external state management library.

### Styling
- Tailwind CSS v4 utility classes only. No CSS Modules, styled-components, or inline `style` props (except where unavoidable).
- The design is a dark theme; hardcoded hex colors (`#0f0f11`, `#1a1a1f`, `#6c63ff`, etc.) are used in Tailwind arbitrary values.

### Error handling
- Use `try/catch/finally` in async event handlers. On error, render a fallback assistant message rather than throwing to the top level.

### ESLint rules (enforced)
- `no-unused-vars`: error, with `varsIgnorePattern: '^[A-Z_]'` (uppercase vars/constants are exempt).
- `react-hooks/rules-of-hooks` and `react-refresh` plugin rules are active.
- Run `npm run lint` before committing frontend changes.

---

## Environment Variables

### `mcp-server/.env`

```
GEMINI_API_KEY=...

AUTH0_DOMAIN=dev-xxxx.us.auth0.com        # Auth0 app domain
AUTH0_CLIENT_ID=...                        # Auth0 app Client ID
AUTH0_CLIENT_SECRET=...                    # Auth0 app Client Secret
AUTH0_AUDIENCE=https://omniclaw.api        # Auth0 API identifier

BASE_URL=http://localhost:8000             # Public URL of this server (used in OAuth metadata)
FRONTEND_URL=http://localhost:5173         # Public URL of the frontend (used in account-status link_url)
# MCP_HOST=0.0.0.0                        # Optional: bind host (default: localhost)
# JWT_SIGNING_KEY=...                      # Optional: stable key so client registrations survive restarts
```

### `frontend/.env`

```
VITE_AUTH0_DOMAIN=dev-xxxx.us.auth0.com
VITE_AUTH0_CLIENT_ID=...
VITE_AUTH0_AUDIENCE=https://omniclaw.api
# VITE_BACKEND_URL=http://localhost:8000   # Optional: defaults to localhost:8000
```

---

## Docker

Build and run the MCP server container:

```bash
docker build -t omniclaw-mcp ./mcp-server
docker run -p 8000:8000 --env-file mcp-server/.env omniclaw-mcp
```

Note: the Dockerfile is currently outdated (wrong Python version, missing source files). Do not rely on it without fixing it first.

---

## Guidelines

- Make incremental commits rather than a massive singular commit.
