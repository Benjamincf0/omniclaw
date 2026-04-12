from __future__ import annotations

import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .config import load_config
from .contracts import ChatRequest, ChatResponse, HealthResponse
from .service import ChatService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    # Store config and service in app.state so we can reload them
    config = load_config()
    service = ChatService.from_config(config)

    app = FastAPI(title="Omniclaw Orchestrator", version="0.1.0")
    app.state.config = config
    app.state.service = service

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        svc = app.state.service
        cfg = app.state.config
        return HealthResponse(
            status="ok",
            mcp_servers=[server.name for server in cfg.mcp_servers],
            default_provider=svc.default_provider,
            default_model=svc.default_model,
            available_providers=svc.available_providers(),
        )

    @app.post("/reload")
    async def reload_config() -> dict[str, str]:
        """Reload configuration from .env file without restarting the server."""
        # Find and reload the .env file
        env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
        load_dotenv(env_path, override=True)
        
        old_provider = app.state.service.default_provider
        old_model = app.state.service.default_model
        
        # Reload config and rebuild service
        app.state.config = load_config()
        app.state.service = ChatService.from_config(app.state.config)
        
        new_provider = app.state.service.default_provider
        new_model = app.state.service.default_model
        
        logger.info(f"Config reloaded:")
        logger.info(f"  Provider: {old_provider} → {new_provider}")
        logger.info(f"  Model: {old_model} → {new_model}")
        
        return {
            "status": "reloaded",
            "old_provider": old_provider,
            "new_provider": new_provider,
            "old_model": old_model,
            "new_model": new_model,
        }

    @app.post("/chat", response_model=ChatResponse)
    async def chat(request: ChatRequest) -> ChatResponse:
        svc = app.state.service
        # Log the current MODEL_PROVIDER env var and service config
        env_provider = os.getenv("MODEL_PROVIDER", "openai")
        logger.info(f"Chat request received:")
        logger.info(f"  MODEL_PROVIDER env: {env_provider}")
        logger.info(f"  Service default provider: {svc.default_provider}")
        logger.info(f"  Service default model: {svc.default_model}")
        logger.info(f"  Request provider: {request.provider or '(use default)'}")
        logger.info(f"  Request model: {request.model or '(use default)'}")
        try:
            return await svc.chat(request)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @app.delete("/sessions/{session_id}")
    async def delete_session(session_id: str) -> dict[str, str]:
        app.state.service.clear_session(session_id)
        return {"status": "cleared", "session_id": session_id}

    return app


app = create_app()
