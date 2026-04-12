from __future__ import annotations

from typing import Any

import httpx


class OrchestratorClient:
    def __init__(self, *, base_url: str, timeout_seconds: float) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=timeout_seconds,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def health(self) -> dict[str, Any]:
        response = await self._client.get("/health")
        return self._decode_json_dict(response)

    async def chat(
        self,
        *,
        session_id: str,
        user_id: str,
        user_name: str,
        message: str,
        provider: str | None = None,
        model: str | None = None,
    ) -> dict[str, Any]:
        response = await self._client.post(
            "/chat",
            json={
                "session_id": session_id,
                "user_id": user_id,
                "user_name": user_name,
                "message": message,
                "provider": provider,
                "model": model,
            },
        )
        return self._decode_json_dict(response)

    async def clear_session(self, session_id: str) -> dict[str, Any]:
        response = await self._client.delete(f"/sessions/{session_id}")
        return self._decode_json_dict(response)

    def _decode_json_dict(self, response: httpx.Response) -> dict[str, Any]:
        if response.status_code >= 400:
            raise RuntimeError(
                f"Orchestrator request failed with {response.status_code}: {response.text}"
            )
        data = response.json()
        if not isinstance(data, dict):
            raise RuntimeError("Orchestrator returned an invalid response payload")
        return data
