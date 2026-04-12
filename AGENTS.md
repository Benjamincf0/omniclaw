# AGENTS.md

This repo contains **Omniclaw** — a John Abbott College Omnivox assistant consisting of:
- `mcp-server/` — Python FastMCP + FastAPI backend (MCP tools + Gemini chat endpoint)
- `frontend/` — React/Vite chat UI

## Project Context

Omnivox authenticates via a token sent in the **request body** (not headers). The server reads the token from `auth.txt`; if missing or invalid, it launches a Playwright browser to intercept and capture a fresh token. See the comment at the top of `a_news.html` for the example `curl` command showing the body token pattern.

---

## Commands

### Python backend (`mcp-server/`)

All Python commands use `uv`. Always run from the `mcp-server/` directory.

| Task | Command |
|---|---|
| Install dependencies | `uv sync` |
| Start MCP/FastAPI server | `uv run omni.py` |
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
│   ├── omni.py            # Main server: FastMCP tools + FastAPI /chat + /health
│   ├── omnivox_client.py  # Authenticated httpx client (reads auth.txt, retries)
│   ├── auth_manager.py    # Playwright-based auth token capture
│   ├── models/
│   │   └── news.py        # Pydantic models + BeautifulSoup HTML parsing
│   ├── test_news.py        # Integration smoke test for news fetching
│   └── test_server.py      # HTTP-level smoke test for auth/retry flow
└── frontend/
    └── src/
        ├── App.jsx           # Root component: state, Gemini history, fetch logic
        └── components/       # Header, Message, ChatInput, QuickChips, WelcomeScreen, TypingIndicator
```

### Key runtime behavior
- The FastMCP server can run in MCP transport mode (`mcp.run(transport="http", ...)`) or as a plain FastAPI app via uvicorn. The active mode is toggled by commenting/uncommenting lines in `main()`.
- The `/chat` endpoint proxies messages to Gemini (`gemini-2.5-flash`) with conversation history and a system prompt.
- Gemini retries up to 3 times with exponential backoff (1s, 2s) on `429 / RESOURCE_EXHAUSTED`.

---

## Python Code Style

### Imports
Order: stdlib → third-party → local. Use `from __future__ import annotations` in modules with forward references (e.g. `models/news.py`).

```python
import asyncio
import os

import httpx
from pydantic import BaseModel

from models.news import AllNewsReq, AllNewsRes
from omnivox_client import omnivox_request
```

### Naming
- `snake_case` for functions, variables, and module-level constants that are internal.
- `SCREAMING_SNAKE_CASE` for true constants (`SYSTEM_PROMPT`, `host` is an exception — follow existing file conventions).
- `PascalCase` for all classes, especially Pydantic models (`ChatRequest`, `AllNewsRes`).
- Prefix private helpers with `_` (`_build_headers`, `_is_auth_failure`, `_normalize_text`).

### Types
- Add type hints to all function signatures.
- Use modern union syntax: `str | None`, not `Optional[str]`.
- Use lowercase generics: `list[str]`, `dict[str, str]` (Python 3.10+).
- All request/response shapes are Pydantic `BaseModel` subclasses.

### Async
- All functions that touch Omnivox or external APIs must be `async def`.
- Use `asyncio.sleep` for backoff; never use blocking `time.sleep` in async code.

### Error handling
- Raise semantically appropriate exceptions: `ValueError` for bad input/config, `RuntimeError` for auth failures, `PermissionError` after all retries exhausted.
- In FastAPI routes, convert exceptions to `HTTPException` with an appropriate status code.
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

Create `mcp-server/.env` (gitignored):

```
GEMINI_API_KEY=...
AUTH0_CONFIG_URL=https://<your-domain>.auth0.com/.well-known/openid-configuration
AUTH0_CLIENT_ID=...
AUTH0_CLIENT_SECRET=...
AUTH0_AUDIENCE=https://<your-domain>.auth0.com/api/v2/
AUTH0_BASE_URL=http://localhost:8000   # optional, defaults to "http://localhost:8000"
MCP_HOST=localhost                     # optional, defaults to "localhost"
# MCP_TOKEN=...                        # used by StaticTokenVerifier (currently commented out)
```

Frontend reads `VITE_BACKEND_URL` (defaults to `http://localhost:8000` if unset).

---

## Docker

Build and run the MCP server container:

```bash
docker build -t omniclaw-mcp ./mcp-server
docker run -p 8000:8000 --env-file mcp-server/.env omniclaw-mcp
```
