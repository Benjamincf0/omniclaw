from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(slots=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(slots=True)
class ChatCompletionResult:
    assistant_message: dict[str, Any]
    text: str
    tool_calls: list[ToolCall]


def _chat_completions_url(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/chat/completions"


def _normalize_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "text" and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "\n".join(parts).strip()
    return ""


def _parse_tool_calls(raw_tool_calls: Any) -> list[ToolCall]:
    parsed: list[ToolCall] = []
    if not isinstance(raw_tool_calls, list):
        return parsed

    for item in raw_tool_calls:
        if not isinstance(item, dict):
            continue
        function = item.get("function")
        if not isinstance(function, dict):
            continue
        name = function.get("name")
        call_id = item.get("id")
        raw_arguments = function.get("arguments", "{}")
        if not isinstance(name, str) or not isinstance(call_id, str):
            continue
        if isinstance(raw_arguments, str):
            arguments = json.loads(raw_arguments or "{}")
        elif isinstance(raw_arguments, dict):
            arguments = raw_arguments
        else:
            raise ValueError(f"Unsupported tool-call arguments for {name}")
        if not isinstance(arguments, dict):
            raise ValueError(f"Tool-call arguments for {name} must decode to an object")
        parsed.append(ToolCall(id=call_id, name=name, arguments=arguments))
    return parsed


class OpenAICompatibleChatClient:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        temperature: float = 0.2,
        timeout_seconds: float = 60.0,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._temperature = temperature
        self._timeout_seconds = timeout_seconds

    async def complete(
        self, *, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> ChatCompletionResult:
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": self._temperature,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        url = _chat_completions_url(self._base_url)

        async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
            response = await client.post(url, headers=headers, json=payload)

        if response.status_code >= 400:
            raise RuntimeError(
                f"Model request failed with {response.status_code}: {response.text}"
            )

        data = response.json()
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise RuntimeError("Model response did not include choices")

        message = choices[0].get("message")
        if not isinstance(message, dict):
            raise RuntimeError("Model response did not include an assistant message")

        assistant_message = {
            "role": "assistant",
            "content": message.get("content"),
        }
        if message.get("tool_calls") is not None:
            assistant_message["tool_calls"] = message["tool_calls"]

        return ChatCompletionResult(
            assistant_message=assistant_message,
            text=_normalize_content(message.get("content")),
            tool_calls=_parse_tool_calls(message.get("tool_calls")),
        )
