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
│  3. Enter Omnivox email + password on /setup page               │
│  4. Backend runs headless Playwright, logs into Omnivox,        │
│     captures cookies, stores them in user_tokens.json           │
│  5. Redirected to /  — chat interface is now active             │
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

---

## Repository structure

```
omniclaw/
├── mcp-server/               # Python backend
│   ├── omni.py               # Main server: FastMCP tools + FastAPI endpoints
│   ├── omnivox_client.py     # Authenticated httpx client (per-user + legacy)
│   ├── auth_manager.py       # Playwright login: interactive + headless
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
    │   ├── App.jsx            # Router: /auth → /setup → / (chat)
    │   └── components/
    │       ├── AuthPage.jsx   # Login / create account (Auth0)
    │       ├── SetupPage.jsx  # Omnivox credentials form
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
| Language | Python 3.11+ (backend), JavaScript/JSX (frontend) |
| Package manager | `uv` (backend), `npm` (frontend) |
| MCP framework | FastMCP ≥ 3.2 |
| Web framework | FastAPI (mounted inside FastMCP) |
| Identity / OAuth2 | Auth0 (OAuthProxy for MCP clients, Auth0 React SDK for frontend) |
| Browser automation | Playwright (headless + headed) |
| AI model | Gemini 2.5 Flash (via Google GenAI SDK) |
| HTML scraping | BeautifulSoup4 + httpx |
| JWT validation | python-jose |
| Frontend build | Vite 8 + React 19 + Tailwind CSS v4 |
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

BASE_URL=http://localhost:8000             # Public URL of this server
# MCP_HOST=0.0.0.0                        # Optional: bind host for MCP transport
# JWT_SIGNING_KEY=...                      # Optional: stable key for client registrations
```

**Where to find these in the Auth0 dashboard:**
- `AUTH0_DOMAIN` and `AUTH0_CLIENT_ID` / `AUTH0_CLIENT_SECRET`: Applications → Applications → your app → Settings tab
- `AUTH0_AUDIENCE`: Applications → APIs → your API → Settings tab (the "API Audience" / "Identifier" field)

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
5. Go to **Applications → APIs** → create an API with identifier `https://omniclaw.api` (or whatever you set as `AUTH0_AUDIENCE`).
6. Copy Domain, Client ID, Client Secret into both `.env` files.

---

## Student onboarding flow (web UI)

1. Student visits `http://localhost:5173`
2. Redirected to `/auth` — clicks **Create account** or **Sign in** (Auth0)
3. After Auth0 login, frontend calls `GET /account-status` with the JWT
4. If Omnivox not yet linked → redirected to `/setup`
5. Student enters their Omnivox email + password and clicks **Connect Omnivox**
6. Backend (`POST /setup-omnivox`) runs a headless Playwright browser, fills the Omnivox login form, captures session cookies, stores them in `user_tokens.json` under the student's Auth0 `sub`
7. Student is redirected to `/` — the chat interface — and can now ask questions about their Omnivox
8. The **Header** shows the student's Auth0 avatar. Clicking it reveals **Reconnect Omnivox** (re-runs setup) and **Sign out**

---

## MCP client onboarding flow (Claude Desktop etc.)

1. In Claude Desktop settings, add an MCP server with URL `http://localhost:8000/mcp`
2. Claude opens a browser → student logs in with Auth0 → JWT issued to Claude
3. Student asks Claude something like "do I have any new messages?" — Claude calls the `get_mio` tool
4. If Omnivox not yet linked: the tool returns an error telling the student to use the web UI (`http://localhost:5173`) to connect their account first
5. Once linked via the web UI, all tool calls work automatically

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

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/chat` | none | Gemini chat proxy (used by the React frontend) |
| `GET` | `/health` | none | Liveness probe |
| `GET` | `/account-status` | Bearer JWT | Returns `{ linked: bool }` for the calling user |
| `POST` | `/setup-omnivox` | Bearer JWT | Accepts `{ email, password }`, runs headless Playwright login, stores cookies |
| `GET` | `/link-omnivox?token=` | JWT query param | Legacy browser-based Omnivox login (headed Playwright) |
| `DELETE` | `/link-omnivox?token=` | JWT query param | Remove stored Omnivox cookies for the user |

---

## Key implementation details

### Why Playwright?
Omnivox has no API. It is a classic server-rendered web app that sets session cookies after a POST login form submission. Playwright lets us automate that form, capture the `Cookie` header from outgoing requests, and reuse it in subsequent httpx requests without a browser.

### Headless vs. headed
- **Headed** (`authenticate`, `authenticate_for_user`): opens a visible browser window. Used for the legacy `/link-omnivox` flow and local dev.
- **Headless** (`authenticate_headless`): fills the form programmatically. Used by `POST /setup-omnivox` so it works on a server with no display.

### Cookie storage
`user_tokens.json` maps Auth0 `sub` → Omnivox cookie string. Reads/writes are protected by an `asyncio.Lock`. On cookie expiry, the next request detects the auth failure (redirect to login page) and triggers a re-login for that user.

### Auth for MCP clients
FastMCP's `OAuthProxy` sits in front of Auth0. MCP clients do Dynamic Client Registration against the proxy, which forwards the OAuth dance to Auth0 using the pre-registered app credentials. The resulting JWT is validated on every tool call via Auth0's JWKS endpoint. The `sub` claim identifies the user.

### Auth for the web frontend
The React app uses `@auth0/auth0-react` with Authorization Code + PKCE. After login, `getAccessTokenSilently()` returns a JWT that is sent as `Authorization: Bearer` on every call to `/setup-omnivox` and `/account-status`.

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
| Manual Omnivox login (legacy) | `uv run python auth_manager.py` |
