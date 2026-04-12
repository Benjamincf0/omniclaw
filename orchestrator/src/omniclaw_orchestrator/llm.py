from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import quote

import httpx

from .config import ModelProviderConfig, normalize_model_provider
from .mcp_client import ExposedTool


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


@dataclass(slots=True)
class ResolvedChatClient:
    provider: str
    model: str
    client: "ChatClient"


class ChatClient(Protocol):
    async def complete(
        self, *, messages: list[dict[str, Any]], tools: list[ExposedTool]
    ) -> ChatCompletionResult: ...


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


def _tool_call_message(tool_call: ToolCall) -> dict[str, Any]:
    return {
        "id": tool_call.id,
        "type": "function",
        "function": {
            "name": tool_call.name,
            "arguments": json.dumps(tool_call.arguments, ensure_ascii=True),
        },
    }


def _assistant_message(
    *, text: str, tool_calls: list[ToolCall]
) -> dict[str, Any]:
    message: dict[str, Any] = {
        "role": "assistant",
        "content": text or None,
    }
    if tool_calls:
        message["tool_calls"] = [_tool_call_message(tool_call) for tool_call in tool_calls]
    return message


def _safe_json_object(raw: Any, *, field_name: str) -> dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        decoded = json.loads(raw or "{}")
        if isinstance(decoded, dict):
            return decoded
    raise ValueError(f"{field_name} must be an object")


def _split_system_messages(
    messages: list[dict[str, Any]],
) -> tuple[str, list[dict[str, Any]]]:
    system_parts: list[str] = []
    conversation: list[dict[str, Any]] = []
    for message in messages:
        if message.get("role") == "system":
            text = _normalize_content(message.get("content"))
            if text:
                system_parts.append(text)
            continue
        conversation.append(message)
    return "\n\n".join(system_parts).strip(), conversation


def _message_tool_calls(message: dict[str, Any]) -> list[ToolCall]:
    return _parse_tool_calls(message.get("tool_calls"))


def _append_block_message(
    messages: list[dict[str, Any]], *, role: str, blocks: list[dict[str, Any]]
) -> None:
    if not blocks:
        return
    if messages and messages[-1].get("role") == role:
        messages[-1]["content"].extend(blocks)
        return
    messages.append({"role": role, "content": blocks})


def _to_anthropic_messages(
    messages: list[dict[str, Any]],
) -> tuple[str, list[dict[str, Any]]]:
    system_prompt, conversation = _split_system_messages(messages)
    anthropic_messages: list[dict[str, Any]] = []

    for message in conversation:
        role = message.get("role")
        if role == "user":
            text = _normalize_content(message.get("content"))
            if text:
                _append_block_message(
                    anthropic_messages,
                    role="user",
                    blocks=[{"type": "text", "text": text}],
                )
            continue

        if role == "assistant":
            blocks: list[dict[str, Any]] = []
            text = _normalize_content(message.get("content"))
            if text:
                blocks.append({"type": "text", "text": text})
            for tool_call in _message_tool_calls(message):
                blocks.append(
                    {
                        "type": "tool_use",
                        "id": tool_call.id,
                        "name": tool_call.name,
                        "input": tool_call.arguments,
                    }
                )
            _append_block_message(anthropic_messages, role="assistant", blocks=blocks)
            continue

        if role == "tool":
            tool_call_id = str(message.get("tool_call_id", "")).strip()
            if not tool_call_id:
                continue
            _append_block_message(
                anthropic_messages,
                role="user",
                blocks=[
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_call_id,
                        "content": _normalize_content(message.get("content")),
                    }
                ],
            )

    return system_prompt, anthropic_messages


def _tool_output_to_gemini_response(raw_content: Any) -> dict[str, Any]:
    if isinstance(raw_content, str):
        try:
            decoded = json.loads(raw_content)
        except json.JSONDecodeError:
            return {"content": raw_content}
        if isinstance(decoded, dict):
            return decoded
        return {"content": decoded}
    if isinstance(raw_content, dict):
        return raw_content
    if isinstance(raw_content, list):
        return {"content": raw_content}
    return {"content": str(raw_content)}


def _append_gemini_content(
    contents: list[dict[str, Any]], *, role: str, parts: list[dict[str, Any]]
) -> None:
    if not parts:
        return
    if contents and contents[-1].get("role") == role:
        contents[-1]["parts"].extend(parts)
        return
    contents.append({"role": role, "parts": parts})


def _to_gemini_contents(
    messages: list[dict[str, Any]],
) -> tuple[str, list[dict[str, Any]]]:
    system_prompt, conversation = _split_system_messages(messages)
    contents: list[dict[str, Any]] = []

    for message in conversation:
        role = message.get("role")
        if role == "user":
            text = _normalize_content(message.get("content"))
            if text:
                _append_gemini_content(
                    contents,
                    role="user",
                    parts=[{"text": text}],
                )
            continue

        if role == "assistant":
            parts: list[dict[str, Any]] = []
            text = _normalize_content(message.get("content"))
            if text:
                parts.append({"text": text})
            for tool_call in _message_tool_calls(message):
                parts.append(
                    {
                        "functionCall": {
                            "name": tool_call.name,
                            "args": tool_call.arguments,
                        }
                    }
                )
            _append_gemini_content(contents, role="model", parts=parts)
            continue

        if role == "tool":
            name = str(message.get("name", "")).strip()
            if not name:
                continue
            _append_gemini_content(
                contents,
                role="user",
                parts=[
                    {
                        "functionResponse": {
                            "name": name,
                            "response": _tool_output_to_gemini_response(
                                message.get("content")
                            ),
                        }
                    }
                ],
            )

    return system_prompt, contents


def _anthropic_messages_url(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    if normalized.endswith("/v1"):
        return f"{normalized}/messages"
    return f"{normalized}/v1/messages"


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
        self, *, messages: list[dict[str, Any]], tools: list[ExposedTool]
    ) -> ChatCompletionResult:
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": self._temperature,
        }
        if tools:
            payload["tools"] = [tool.as_openai_tool() for tool in tools]
            payload["tool_choice"] = "auto"

        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
            response = await client.post(
                f"{self._base_url}/chat/completions",
                headers=headers,
                json=payload,
            )

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

        tool_calls = _parse_tool_calls(message.get("tool_calls"))
        return ChatCompletionResult(
            assistant_message=_assistant_message(
                text=_normalize_content(message.get("content")),
                tool_calls=tool_calls,
            ),
            text=_normalize_content(message.get("content")),
            tool_calls=tool_calls,
        )


class AnthropicChatClient:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        temperature: float,
        max_output_tokens: int,
        timeout_seconds: float = 60.0,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._temperature = temperature
        self._max_output_tokens = max_output_tokens
        self._timeout_seconds = timeout_seconds

    async def complete(
        self, *, messages: list[dict[str, Any]], tools: list[ExposedTool]
    ) -> ChatCompletionResult:
        system_prompt, anthropic_messages = _to_anthropic_messages(messages)
        payload: dict[str, Any] = {
            "model": self._model,
            "max_tokens": self._max_output_tokens,
            "messages": anthropic_messages,
            "temperature": self._temperature,
        }
        if system_prompt:
            payload["system"] = system_prompt
        if tools:
            payload["tools"] = [tool.as_anthropic_tool() for tool in tools]
            payload["tool_choice"] = {"type": "auto"}

        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
            response = await client.post(
                _anthropic_messages_url(self._base_url),
                headers=headers,
                json=payload,
            )

        if response.status_code >= 400:
            raise RuntimeError(
                f"Model request failed with {response.status_code}: {response.text}"
            )

        data = response.json()
        content = data.get("content")
        if not isinstance(content, list):
            raise RuntimeError("Model response did not include content blocks")

        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        for index, block in enumerate(content, start=1):
            if not isinstance(block, dict):
                continue
            block_type = block.get("type")
            if block_type == "text" and isinstance(block.get("text"), str):
                text_parts.append(block["text"])
                continue
            if block_type == "tool_use":
                name = block.get("name")
                if not isinstance(name, str) or not name:
                    continue
                tool_calls.append(
                    ToolCall(
                        id=str(block.get("id") or f"claude-call-{index}"),
                        name=name,
                        arguments=_safe_json_object(
                            block.get("input"),
                            field_name=f"tool input for {name}",
                        ),
                    )
                )

        text = "\n".join(part for part in text_parts if part).strip()
        return ChatCompletionResult(
            assistant_message=_assistant_message(text=text, tool_calls=tool_calls),
            text=text,
            tool_calls=tool_calls,
        )


class GeminiChatClient:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        temperature: float,
        max_output_tokens: int,
        timeout_seconds: float = 60.0,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._temperature = temperature
        self._max_output_tokens = max_output_tokens
        self._timeout_seconds = timeout_seconds

    async def complete(
        self, *, messages: list[dict[str, Any]], tools: list[ExposedTool]
    ) -> ChatCompletionResult:
        system_prompt, contents = _to_gemini_contents(messages)
        payload: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": self._temperature,
                "maxOutputTokens": self._max_output_tokens,
            },
        }
        if system_prompt:
            payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}
        if tools:
            payload["tools"] = [
                {
                    "functionDeclarations": [
                        tool.as_gemini_function_declaration() for tool in tools
                    ]
                }
            ]
            payload["toolConfig"] = {
                "functionCallingConfig": {
                    "mode": "AUTO",
                }
            }

        url = (
            f"{self._base_url}/models/{quote(self._model, safe='')}:generateContent"
            f"?key={quote(self._api_key, safe='')}"
        )
        headers = {"Content-Type": "application/json"}

        async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
            response = await client.post(url, headers=headers, json=payload)

        if response.status_code >= 400:
            raise RuntimeError(
                f"Model request failed with {response.status_code}: {response.text}"
            )

        data = response.json()
        candidates = data.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            raise RuntimeError("Model response did not include candidates")

        candidate = candidates[0]
        if not isinstance(candidate, dict):
            raise RuntimeError("Model response did not include a valid candidate")

        content = candidate.get("content")
        if not isinstance(content, dict):
            raise RuntimeError("Model response did not include candidate content")

        parts = content.get("parts")
        if not isinstance(parts, list):
            raise RuntimeError("Model response did not include candidate parts")

        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        for index, part in enumerate(parts, start=1):
            if not isinstance(part, dict):
                continue
            text = part.get("text")
            if isinstance(text, str):
                text_parts.append(text)
            function_call = part.get("functionCall")
            if not isinstance(function_call, dict):
                continue
            name = function_call.get("name")
            if not isinstance(name, str) or not name:
                continue
            tool_calls.append(
                ToolCall(
                    id=str(function_call.get("id") or f"gemini-call-{index}"),
                    name=name,
                    arguments=_safe_json_object(
                        function_call.get("args"),
                        field_name=f"tool args for {name}",
                    ),
                )
            )

        text = "\n".join(part for part in text_parts if part).strip()
        return ChatCompletionResult(
            assistant_message=_assistant_message(text=text, tool_calls=tool_calls),
            text=text,
            tool_calls=tool_calls,
        )


class ModelClientRegistry:
    def __init__(
        self,
        *,
        default_provider: str,
        provider_configs: dict[str, ModelProviderConfig],
    ) -> None:
        self._default_provider = normalize_model_provider(default_provider)
        self._provider_configs = provider_configs
        self._clients: dict[tuple[str, str], ChatClient] = {}

    @property
    def default_provider(self) -> str:
        return self._default_provider

    def default_model(self) -> str:
        return self._provider_configs[self._default_provider].default_model

    def available_providers(self) -> list[str]:
        available: list[str] = []
        for provider, config in self._provider_configs.items():
            if provider == "ollama":
                available.append(provider)
                continue
            if config.api_key:
                available.append(provider)
        return available

    def resolve(
        self, *, provider: str | None = None, model: str | None = None
    ) -> ResolvedChatClient:
        resolved_provider = normalize_model_provider(provider or self._default_provider)
        provider_config = self._provider_configs[resolved_provider]
        resolved_model = (model or provider_config.default_model).strip()
        if not resolved_model:
            raise ValueError(
                f"No default model is configured for provider '{resolved_provider}'. "
                "Pass model explicitly or configure the provider's *_MODEL env var."
            )
        client_key = (resolved_provider, resolved_model)
        client = self._clients.get(client_key)
        if client is None:
            client = self._build_client(provider_config, model=resolved_model)
            self._clients[client_key] = client
        return ResolvedChatClient(
            provider=resolved_provider,
            model=resolved_model,
            client=client,
        )

    def _build_client(
        self, provider_config: ModelProviderConfig, *, model: str
    ) -> ChatClient:
        provider = provider_config.provider
        if provider == "openai":
            if not provider_config.api_key:
                raise ValueError("OPENAI_API_KEY is required for provider 'openai'")
            return OpenAICompatibleChatClient(
                api_key=provider_config.api_key,
                base_url=provider_config.base_url,
                model=model,
                temperature=provider_config.temperature,
            )

        if provider == "ollama":
            return OpenAICompatibleChatClient(
                api_key=provider_config.api_key,
                base_url=provider_config.base_url,
                model=model,
                temperature=provider_config.temperature,
            )

        if provider == "claude":
            if not provider_config.api_key:
                raise ValueError("ANTHROPIC_API_KEY is required for provider 'claude'")
            return AnthropicChatClient(
                api_key=provider_config.api_key,
                base_url=provider_config.base_url,
                model=model,
                temperature=provider_config.temperature,
                max_output_tokens=provider_config.max_output_tokens,
            )

        if provider == "gemini":
            if not provider_config.api_key:
                raise ValueError("GEMINI_API_KEY is required for provider 'gemini'")
            return GeminiChatClient(
                api_key=provider_config.api_key,
                base_url=provider_config.base_url,
                model=model,
                temperature=provider_config.temperature,
                max_output_tokens=provider_config.max_output_tokens,
            )

        raise ValueError(f"Unsupported provider '{provider}'")
