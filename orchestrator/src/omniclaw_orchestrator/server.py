from __future__ import annotations

from fastapi import FastAPI, HTTPException

from .config import load_config
from .contracts import ChatRequest, ChatResponse, HealthResponse
from .service import ChatService


def create_app() -> FastAPI:
    config = load_config()
    service = ChatService.from_config(config)

    app = FastAPI(title="Omniclaw Orchestrator", version="0.1.0")

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            mcp_servers=[server.name for server in config.mcp_servers],
            default_provider=service.default_provider,
            default_model=service.default_model,
            available_providers=service.available_providers(),
        )

    @app.post("/chat", response_model=ChatResponse)
    async def chat(request: ChatRequest) -> ChatResponse:
        try:
            return await service.chat(request)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @app.delete("/sessions/{session_id}")
    async def delete_session(session_id: str) -> dict[str, str]:
        service.clear_session(session_id)
        return {"status": "cleared", "session_id": session_id}

    return app


app = create_app()
