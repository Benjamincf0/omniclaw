from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


class OrchestratorClient:
    def __init__(self, *, base_url: str, timeout_seconds: float) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/health")

    def chat(
        self,
        *,
        session_id: str,
        user_id: str,
        user_name: str,
        message: str,
        provider: str | None = None,
        model: str | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/chat",
            {
                "session_id": session_id,
                "user_id": user_id,
                "user_name": user_name,
                "message": message,
                "provider": provider,
                "model": model,
            },
        )

    def clear_session(self, session_id: str) -> dict[str, Any]:
        encoded_session_id = urllib.parse.quote(session_id, safe="")
        return self._request("DELETE", f"/sessions/{encoded_session_id}")

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        data = None
        headers: dict[str, str] = {}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        request = urllib.request.Request(
            f"{self._base_url}{path}",
            data=data,
            headers=headers,
            method=method,
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=self._timeout_seconds,
            ) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"Orchestrator request failed with {exc.code}: {detail}"
            ) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Could not reach orchestrator: {exc.reason}") from exc

        try:
            decoded = json.loads(body)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Orchestrator returned invalid JSON") from exc
        if not isinstance(decoded, dict):
            raise RuntimeError("Orchestrator returned an invalid response payload")
        return decoded
