# AGENTS.md

## What is Omniclaw?

Omniclaw is a multi-tenant AI assistant for John Abbott College (JAC) students. It connects to a student's Omnivox account and lets them interact with it through natural language — reading MIO messages, fetching college news, and eventually sending messages — via a web chat interface or any MCP-compatible AI client (e.g. Claude Desktop).

Omnivox has no public API. Omniclaw works by automating a real browser login with Playwright to capture the student's session cookies, then replaying those cookies on subsequent HTTP requests to scrape and parse Omnivox pages.

---

## How it works — full picture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Student browser                          │
│                                                                 │
│  1. Visit http://localhost:5173                                  │
│  2. Click "Create account" → Auth0 login/signup                 │
│  3. Enter Omnivox student ID + password on /setup page          │
│  4. Backend runs Playwright in background, fills login form     │
│  5. If Omnivox requires 2FA: frontend shows code input,         │
│     student submits code, Playwright fills it in and continues  │
│  6. Cookies captured and stored in user_tokens.json             │
│  7. Redirected to /  — chat interface is now active             │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                  MCP client (Claude Desktop etc.)               │
│                                                                 │
│  1. Add http://localhost:8000/mcp as an MCP server              │
│  2. Client discovers OAuth2 metadata, opens Auth0 login         │
│  3. Student logs in with Auth0 → gets a JWT access token        │
│  4. Every tool call sends:  Authorization: Bearer <jwt>         │
│  5. Server validates JWT → extracts user_id (Auth0 sub)         │
│  6. Looks up that user's Omnivox cookies in user_tokens.json    │
│  7. Makes authenticated Omnivox requests with those cookies     │
│  8. Returns parsed data to the AI client                        │
└─────────────────────────────────────────────────────────────────┘
```

One Auth0 account links to one set of Omnivox cookies. Multiple students can use the same server instance independently.

If a user's Omnivox account is not yet linked, `get_account_status()` returns a `link_url` pointing at `{FRONTEND_URL}/setup`. The student opens that URL, logs in with Auth0 (same identity), enters their credentials, and the backend captures and stores their cookies. After that, all MCP tool calls work automatically.

---

## Repository structure

```
omniclaw/
├── mcp-server/               # Python backend
│   ├── omni.py               # Main server: FastMCP tools + custom HTTP routes
│   ├── omnivox_client.py     # Authenticated httpx client (per-user + legacy)
│   ├── auth_manager.py       # Playwright login: headed + headless flows
│   ├── user_store.py         # JSON file store: user_id → Omnivox cookie string
│   ├── models/
│   │   ├── news.py           # Pydantic models + BeautifulSoup news scraping
│   │   └── mio.py            # Pydantic models + BeautifulSoup MIO scraping
│   ├── user_tokens.json      # Runtime: per-user Omnivox cookies (gitignored)
│   ├── auth.txt              # Runtime: legacy single-user cookie (gitignored)
│   └── .env                  # Secrets (gitignored) — see required vars below
└── frontend/                 # React/Vite web UI
    ├── src/
    │   ├── main.jsx           # Entry point — mounts Auth0Provider + App
    │   ├── App.jsx            # Router: /auth → /setup|/link-omnivox → / (chat)
    │   └── components/
    │       ├── AuthPage.jsx   # Login / create account (Auth0)
    │       ├── SetupPage.jsx  # Omnivox student ID + password form
    │       ├── Header.jsx     # Top bar: logo, live indicator, user menu
    │       ├── ChatInput.jsx  # Message textarea + send button
    │       ├── Message.jsx    # Individual chat bubble
    │       ├── WelcomeScreen.jsx
    │       ├── QuickChips.jsx
    │       └── TypingIndicator.jsx
    └── .env                  # Vite env vars (Auth0 config)
```

---

## Stack

| Layer | Technology |
|---|---|
| Language | Python 3.12+ (backend), JavaScript/JSX (frontend) |
| Package manager | `uv` (backend), `npm` (frontend) |
| MCP framework | FastMCP ≥ 3.2 |
| HTTP routing | Starlette (`@mcp.custom_route()` — no separate FastAPI app) |
| Identity / OAuth2 | Auth0 (OAuthProxy for MCP clients, Auth0 React SDK for frontend) |
| Browser automation | Playwright (headed for local dev, headless for production) |
| AI model | Gemini 2.5 Flash (via Google GenAI SDK) |
| HTML scraping | BeautifulSoup4 + httpx |
| JWT validation | python-jose |
| Frontend build | Vite + React 19 + Tailwind CSS v4 |
| Animations | Framer Motion |

---

## Running locally

### 1. Backend

```bash
cd mcp-server
uv sync
uv run omni.py
```

Server listens on `http://localhost:8000`.

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend listens on `http://localhost:5173`.

---

## Environment variables

### `mcp-server/.env`

```
GEMINI_API_KEY=...

AUTH0_DOMAIN=dev-xxxx.us.auth0.com        # Auth0 app domain
AUTH0_CLIENT_ID=...                        # Auth0 app Client ID
AUTH0_CLIENT_SECRET=...                    # Auth0 app Client Secret
AUTH0_AUDIENCE=https://omniclaw.api        # Auth0 API identifier

BASE_URL=http://localhost:8000             # Public URL of this server (used in OAuth metadata)
FRONTEND_URL=http://localhost:5173         # Public URL of the frontend (used in link_url)
# MCP_HOST=0.0.0.0                        # Optional: bind host (default: localhost)
# JWT_SIGNING_KEY=...                      # Optional: stable key so client registrations survive restarts
```

**Where to find these in the Auth0 dashboard:**
- `AUTH0_DOMAIN` and `AUTH0_CLIENT_ID` / `AUTH0_CLIENT_SECRET`: Applications → Applications → your app → Settings tab
- `AUTH0_AUDIENCE`: Applications → APIs → your API → Settings tab (the "Identifier" field)

### `frontend/.env`

```
VITE_AUTH0_DOMAIN=dev-xxxx.us.auth0.com   # Same as AUTH0_DOMAIN
VITE_AUTH0_CLIENT_ID=...                  # Same as AUTH0_CLIENT_ID
VITE_AUTH0_AUDIENCE=https://omniclaw.api  # Same as AUTH0_AUDIENCE
# VITE_BACKEND_URL=http://localhost:8000  # Optional: defaults to localhost:8000
```

---

## Auth0 dashboard setup checklist

1. Go to **Applications → Applications** → create or open a **Regular Web Application**.
2. On the Settings tab, add to **Allowed Callback URLs**:
   ```
   http://localhost:8000/auth/callback, http://localhost:5173
   ```
3. Add to **Allowed Logout URLs**:
   ```
   http://localhost:5173/auth
   ```
4. Add to **Allowed Web Origins**:
   ```
   http://localhost:5173
   ```
5. Go to **Applications → APIs** → create an API with identifier matching `AUTH0_AUDIENCE`.
6. Copy Domain, Client ID, Client Secret into both `.env` files.

---

## Student onboarding flow (web UI)

1. Student visits `http://localhost:5173`
2. Redirected to `/auth` — clicks **Create account** or **Sign in** (Auth0)
3. After Auth0 login, frontend calls `GET /account-status` with the JWT
4. If Omnivox not yet linked → redirected to `/setup`
5. Student enters their **Omnivox student ID** (7-digit number) + password and clicks **Connect Omnivox**
6. Frontend posts to `POST /setup-omnivox` (with JWT), receives `{ session_id }` immediately, and begins polling `GET /setup-status?session_id=<id>` every 1.5 s
7. If Omnivox requires 2FA: polling returns `{ status: "needs_otp" }` → frontend shows a verification-code input. Student enters the code → frontend posts to `POST /setup-2fa` → Playwright fills it in and continues
8. Polling detects `{ status: "success" }` → student is redirected to `/`
9. The **Header** shows the student's Auth0 avatar. Clicking it reveals **Reconnect Omnivox** (re-runs setup), **Disconnect Omnivox** (removes stored cookies via `DELETE /unlink-omnivox`), and **Sign out**

---

## MCP client onboarding flow (Claude Desktop etc.)

1. In Claude Desktop settings, add an MCP server with URL `http://localhost:8000/mcp`
2. Claude opens a browser → student logs in with Auth0 → JWT issued to Claude
3. Student asks Claude something like "do I have any new messages?" — Claude calls the `get_mio` tool
4. If Omnivox not yet linked: `get_account_status` returns `linked: false` and a `link_url` pointing to `{FRONTEND_URL}/setup`. The student opens that URL, connects their account via the web UI, then returns to the MCP client.
5. Once linked, all tool calls work automatically

---

## MCP tools

| Tool | Description |
|---|---|
| `get_mio(num)` | Fetch the N most recent MIO (inbox) messages |
| `get_mio_item(link)` | Get the full content of a single MIO |
| `send_mio(subject, message)` | Send an MIO (placeholder — form fields TBD) |
| `get_news(num)` | Fetch the N most recent college news links |
| `get_news_item(link)` | Get the full content of a single news post |
| `get_account_status()` | Check whether the user's Omnivox account is linked |

---

## API endpoints

All HTTP endpoints are registered via `@mcp.custom_route()` on the FastMCP server — they share port 8000 with the MCP protocol. There is no separate FastAPI app.

| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/health` | none | Liveness probe |
| `GET` | `/account-status` | Bearer JWT | Returns `{ linked: bool }` for the calling user |
| `POST` | `/setup-omnivox` | Bearer JWT | Accepts `{ email, password }`, starts background Playwright login, returns `{ session_id }` |
| `GET` | `/setup-status` | none | Poll login progress: `?session_id=<id>` → `{ status: "running"\|"needs_otp"\|"success"\|"error" }` |
| `POST` | `/setup-2fa` | none | Submit 2FA code: `{ session_id, code }` — resumes the paused Playwright task |
| `DELETE` | `/unlink-omnivox` | Bearer JWT | Removes the calling user's stored Omnivox cookies |
| `POST` | `/chat` | none | Gemini chat proxy (used by the React frontend) |

> Note: the `email` field in `/setup-omnivox` carries the student's **7-digit Omnivox student ID**, not an email address. The field is named `email` because that is what the Omnivox login form's `#Identifiant` input accepts.
>
> `/setup-status` and `/setup-2fa` do not require auth — the `session_id` is a 128-bit cryptographically random token (`secrets.token_urlsafe(16)`) that acts as a bearer credential for that specific login session.

---

## Key implementation details

### Why Playwright?
Omnivox has no API. It is a classic server-rendered web app that sets session cookies after a form login. Playwright automates that form, captures the `Cookie` header from outgoing post-login requests, and the cookies are replayed in subsequent httpx requests.

### Headed vs. headless
`authenticate_headless` in `auth_manager.py` currently runs with `headless=False` (visible browser window) for local development and debugging. Change to `headless=True` for server deployments where no display is available.

### Cookie capture strategy
Three tiers in order of preference:
1. Cookies from requests to the specific target module URL
2. Cookies from any post-login Omnivox request
3. All cookies from the browser context as a fallback

### Cookie storage
`user_tokens.json` maps Auth0 `sub` → raw Omnivox cookie string. Reads/writes are protected by an `asyncio.Lock`. On session expiry, the next request detects the auth failure (401/403 or redirect to a login URL pattern) and triggers a re-login for that user, retrying the request once.

### Auth for MCP clients
FastMCP's `OAuthProxy` sits in front of Auth0. MCP clients do Dynamic Client Registration against the proxy, which forwards the OAuth dance to Auth0 using the pre-registered app credentials. The resulting JWT is validated on every tool call via Auth0's JWKS endpoint. The `sub` claim identifies the user.

### Auth for the web frontend
The React app uses `@auth0/auth0-react` with Authorization Code + PKCE. After login, `getAccessTokenSilently()` returns a JWT that is sent as `Authorization: Bearer` on calls to `/setup-omnivox`, `/unlink-omnivox`, and `/account-status`. The JWT is validated server-side using `python-jose` against the same Auth0 JWKS endpoint.

### Browser lock
All Playwright sessions share a single `asyncio.Lock` (`_browser_lock`). Only one browser window opens at a time — fine for low traffic, but a bottleneck under concurrent logins. The lock is held for the entire duration of `authenticate_headless`, including any wait for a 2FA code.

### Two-phase login and 2FA
`POST /setup-omnivox` spawns `asyncio.create_task(_run_login(...))` and returns `{session_id}` without waiting. The task stores progress in a plain dict in `_sessions` (in-memory, not persisted). If `authenticate_headless` detects a 2FA input on the page (via `page.query_selector(_OTP_INPUT_SELECTOR)`), it calls `otp_callback()` which sets `session["status"] = "needs_otp"` and blocks on `asyncio.wait_for(event.wait(), timeout=300)`. `POST /setup-2fa` sets `session["otp"]` and fires the event, unblocking the task. Sessions are deleted from `_sessions` once a terminal status (`"success"` or `"error"`) is read by the polling client.

`_OTP_INPUT_SELECTOR` in `auth_manager.py` must match the actual Omnivox 2FA page's code input element. Verify with DevTools on the 2FA page and update if needed.

---

## Commands reference

| Task | Command |
|---|---|
| Start backend | `uv run omni.py` (from `mcp-server/`) |
| Start frontend | `npm run dev` (from `frontend/`) |
| Install backend deps | `uv sync` |
| Install frontend deps | `npm install` |
| Lint frontend | `npm run lint` |
| Build frontend | `npm run build` |
