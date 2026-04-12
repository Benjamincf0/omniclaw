import asyncio
import os
from functools import lru_cache
from contextlib import asynccontextmanager
from pathlib import Path

from fastmcp import FastMCP

from models.mio import AllMiosReq, AllMiosRes, MioReq, MioRes, get_all_mios
from models.mio import get_mio as fetch_mio
from models.news import AllNewsReq, AllNewsRes, NewsReq, NewsRes, get_all_news
from models.news import get_news as fetch_news
from omnivox_client import omnivox_request
from auth_manager import load_auth

from google import genai
from google.genai import types
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn
from dotenv import load_dotenv

# Load environment variables 
load_dotenv()
# Anyone connecting must send: Authorization: Bearer my-secret-token
# auth = StaticTokenVerifier(
#     tokens={
#         os.environ["MCP_TOKEN"]: {
#             "client_id": "trusted-client",
#             "scopes": ["read", "write"],
#         }
#     }
# )

# Initialize FastMCP server
mcp = FastMCP("omniclaw")

# Constants
MCP_HOST = os.getenv("MCP_HOST", "127.0.0.1").strip() or "127.0.0.1"
MCP_PORT = int(os.getenv("MCP_PORT", "8000"))
MCP_TRANSPORT_PATH = (
    "/" + os.getenv("MCP_TRANSPORT_PATH", "/mcp").strip().strip("/")
).rstrip("/") or "/mcp"


@mcp.tool()
async def get_mio(num: int = 10) -> AllMiosRes:
    """Get MIOs (internal messages) for a student's Omnivox."""
    if num < 1:
        raise ValueError("num must be at least 1")

    mios = await get_all_mios(AllMiosReq())
    return AllMiosRes(mios=mios.mios[:num])


@mcp.tool()
async def get_mio_item(link: str) -> MioRes:
    """Get the contents of a single Omnivox MIO."""
    return await fetch_mio(MioReq(link=link))


@mcp.tool()
async def send_mio(subject: str, message: str) -> str:
    """Send an MIO through a student's Omnivox."""
    # TODO: replace with actual Omnivox send endpoint + proper form fields
    resp = await omnivox_request(
        "/intr/Module/MessagerieEleve/Envoyer.aspx",
        method="POST",
        data={"subject": subject, "message": message},
    )
    return resp.text


@mcp.tool()
async def get_news(num: int = 10) -> AllNewsRes:
    """get the latest student news"""
    if num < 1:
        raise ValueError("num must be at least 1")

    news = await get_all_news(AllNewsReq())
    return AllNewsRes(news_links=news.news_links[:num])


@mcp.tool()
async def get_news_item(link: str) -> NewsRes:
    """get the contents of a single student news post"""
    return await fetch_news(NewsReq(link=link))







# ── Gemini setup ──────────────────────────────────────────────────────────────

TOOL_HANDLERS = {
    "get_mio": get_mio,
    "send_mio": send_mio,
    "get_news": get_news,
    "get_news_item": get_news_item,
}

GEMINI_TOOLS = [
    types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="get_mio",
                description="Get MIOs (internal messages) for a student's Omnivox.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "num": types.Schema(type=types.Type.INTEGER, description="How many MIO messages to fetch."),
                    },
                    required=["num"],
                ),
            ),
            types.FunctionDeclaration(
                name="send_mio",
                description="Send an MIO through a student's Omnivox.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "subject": types.Schema(type=types.Type.STRING, description="Message subject."),
                        "message": types.Schema(type=types.Type.STRING, description="Message body."),
                    },
                    required=["subject", "message"],
                ),
            ),
            types.FunctionDeclaration(
                name="get_news",
                description="Get the latest student news links from John Abbott College.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "num": types.Schema(type=types.Type.INTEGER, description="How many news items to fetch (default 10)."),
                    },
                ),
            ),
            types.FunctionDeclaration(
                name="get_news_item",
                description="Get the full contents of a single news post by its link.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "link": types.Schema(type=types.Type.STRING, description="The news post URL."),
                    },
                    required=["link"],
                ),
            ),
        ]
    )
]


class GeminiConfigurationError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def _get_gemini_client() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise GeminiConfigurationError(
            "GEMINI_API_KEY is required to use the legacy /chat endpoint."
        )
    return genai.Client(api_key=api_key)

SYSTEM_PROMPT = (
    "You are Omniclaw, a helpful assistant for John Abbott College (JAC) students. "
    "You have access to the student's Omnivox account and can fetch messages and news. "
    "Be concise and friendly. Use bullet points for lists. "
    "If you need more information ask a short clarifying question."
)


def _build_contents(message: str, history: list[dict]) -> list[types.Content]:
    """Convert frontend history (plain dicts) + new message into Content objects."""
    contents = []

    for item in history:
        role = item.get("role", "user")
        # Normalise "assistant" → "model" (Gemini expects "model")
        if role == "assistant":
            role = "model"
        # Convert message parts to types.Part, ignoring any parts that don't have text (e.g. tool calls)
        parts = [types.Part(text=p["text"]) for p in item.get("parts", [])]
        if parts:
            contents.append(types.Content(role=role, parts=parts))

    contents.append(types.Content(role="user", parts=[types.Part(text=message)]))
    return contents


async def _generate(contents: list) -> types.GenerateContentResponse:
    """Call Gemini with exponential backoff on rate limit errors."""
    gemini_client = _get_gemini_client()
    for attempt in range(3):
        try:
            return await gemini_client.aio.models.generate_content(
                model="gemini-2.5-flash",
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    tools=GEMINI_TOOLS,
                ),
            )
        except Exception as e:
            if ("429" in str(e) or "RESOURCE_EXHAUSTED" in str(e)) and attempt < 2:
                await asyncio.sleep(2 ** attempt)  # 1s, 2s
                continue
            raise


async def run_chat(message: str, history: list[dict]) -> str:
    """Agentic loop: call Gemini, execute any tool calls, repeat until final text."""
    contents = _build_contents(message, history)

    while True:
        response = await _generate(contents)
        candidate = response.candidates[0].content
        function_calls = [p for p in candidate.parts if p.function_call]

        # No tool calls — Gemini is done
        if not function_calls:
            return "\n".join(p.text for p in candidate.parts if p.text)

        # Append Gemini's response (with tool calls) to the conversation
        contents.append(candidate)

        # Execute each tool and collect results
        tool_results: list[types.Part] = []
        for part in function_calls:
            fc = part.function_call
            handler = TOOL_HANDLERS.get(fc.name)
            if handler:
                result = await handler(**dict(fc.args))
                # Pydantic models need serialisation; strings pass through fine
                if hasattr(result, "model_dump"):
                    result = result.model_dump()
            else:
                result = f"Unknown tool: {fc.name}"

            tool_results.append(
                types.Part.from_function_response(name=fc.name, response={"result": result})
            )

        contents.append(types.Content(role="user", parts=tool_results))


# ── FastAPI app ───────────────────────────────────────────────────────────────

mcp_http_app = mcp.http_app(
    path=MCP_TRANSPORT_PATH,
    transport="streamable-http",
)

app = FastAPI(
    title="Omniclaw API",
    lifespan=mcp_http_app.lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []


class ChatResponse(BaseModel):
    reply: str


@app.post("/chat", response_model=ChatResponse)
async def chat(body: ChatRequest):
    if not body.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")
    try:
        reply = await run_chat(body.message, body.history)
        return ChatResponse(reply=reply)
    except GeminiConfigurationError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        msg = str(e)
        status = 429 if "429" in msg or "RESOURCE_EXHAUSTED" in msg else 502
        raise HTTPException(status_code=status, detail=msg)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "mcp_path": MCP_TRANSPORT_PATH,
        "gemini_chat_enabled": bool(os.getenv("GEMINI_API_KEY", "").strip()),
        "model": "gemini-2.5-flash",
    }


app.mount("/", mcp_http_app)


# ── Static frontend serving ──────────────────────────────────────────────────

_static_dir = Path(__file__).parent / "static"
if _static_dir.is_dir():
    app.mount("/", StaticFiles(directory=str(_static_dir), html=True), name="static")


# ── Entry point ───────────────────────────────────────────────────────────────



def main():
    uvicorn.run(app, host=MCP_HOST, port=MCP_PORT, reload=False)


if __name__ == "__main__":
    main()