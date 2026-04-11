import os
from typing import Any

from fastmcp import FastMCP
from fastmcp.server.auth.providers.jwt import StaticTokenVerifier

from google import genai
from google.genai import types
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from dotenv import load_dotenv

# Load environment variables 
load_dotenv()
# Anyone connecting must send: Authorization: Bearer my-secret-token
auth = StaticTokenVerifier(
    tokens={
        os.environ["MCP_TOKEN"]: {
            "client_id": "trusted-client",
            "scopes": ["read", "write"],
        }
    }
)

# Initialize FastMCP server
mcp = FastMCP("weather", auth=auth)

# Constants


@mcp.tool()
async def get_mio(num: int) -> str:
    """get an MIO for a student's omnivox"""
    return f"\n---\nHELLO WORLD FROM get_mio({num}) heheheh\n---\n"


@mcp.tool()
async def send_mio(subject: str, message: str) -> str:
    """get an MIO for a student's omnivox"""
    return f"\n---\nHELLO WORLD FROM get_subject(subject:{subject}, message:{message}) heheheh\n---\n"


@mcp.tool()
async def get_news(num: int) -> str:
    """get the latest student news"""
    return f"\n---\nHELLO WORLD FROM get_news({num}) heheheh\n---\n"







# ── Gemini setup ──────────────────────────────────────────────────────────────

gemini_client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

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


async def run_chat(message: str, history: list[dict]) -> str:
    """Send message to Gemini and return the text response."""
    contents = _build_contents(message, history)

    response = await gemini_client.aio.models.generate_content(
        model="gemini-2.5-flash",
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            tools=[],  # No tools for now, but we could add some in the future (e.g. calendar access, etc.
        ),
    )

    return "\n".join(p.text for p in response.candidates[0].content.parts if p.text)


# ── FastAPI app ───────────────────────────────────────────────────────────────

app = FastAPI(title="Omniclaw API")

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
    except Exception as e:
        msg = str(e)
        status = 429 if "429" in msg or "RESOURCE_EXHAUSTED" in msg else 502
        raise HTTPException(status_code=status, detail=msg)


@app.get("/health")
async def health():
    return {"status": "ok", "model": "gemini-2.5-flash"}


# ── Entry point ───────────────────────────────────────────────────────────────



def main():
    # run the server
    # mcp.run(transport="http", host="0.0.0.0", port=8000) # turn on MCP server to use the external AI clients 
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False) # run FastAPI server for the frontend to connect to




if __name__ == "__main__":
    main()
