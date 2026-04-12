from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from omniclaw_orchestrator.config import AppConfig, McpServerConfig
from omniclaw_orchestrator.contracts import ChatRequest
from omniclaw_orchestrator.llm import ChatCompletionResult, ToolCall
from omniclaw_orchestrator.service import ChatService, SessionStore


@dataclass
class _FakeLlmClient:
    responses: list[ChatCompletionResult]

    async def complete(
        self, *, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> ChatCompletionResult:
        assert tools
        return self.responses.pop(0)


class _FakeMcpClient:
    async def __aenter__(self) -> _FakeMcpClient:
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        return None

    async def get_openai_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "get_mio",
                    "description": "Fetch MIOs",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        assert name == "get_mio"
        assert arguments == {"num": 5}
        return '{"is_error": false, "content": [{"type": "text", "text": "5 MIOs"}]}'


def _config() -> AppConfig:
    return AppConfig(
        host="127.0.0.1",
        port=8080,
        openai_api_key="test-key",
        openai_base_url="https://example.com/v1",
        openai_model="test-model",
        openai_temperature=0.2,
        mcp_servers=[McpServerConfig(name="omnivox", url="http://localhost:8000/mcp")],
        history_limit=12,
        max_tool_rounds=4,
        system_prompt="Use tools when needed.",
    )


async def test_chat_service_runs_tool_loop_and_persists_history() -> None:
    llm = _FakeLlmClient(
        responses=[
            ChatCompletionResult(
                assistant_message={
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call-1",
                            "type": "function",
                            "function": {
                                "name": "get_mio",
                                "arguments": '{"num": 5}',
                            },
                        }
                    ],
                },
                text="",
                tool_calls=[ToolCall(id="call-1", name="get_mio", arguments={"num": 5})],
            ),
            ChatCompletionResult(
                assistant_message={
                    "role": "assistant",
                    "content": "You have 5 recent MIOs.",
                },
                text="You have 5 recent MIOs.",
                tool_calls=[],
            ),
        ]
    )
    service = ChatService(
        config=_config(),
        llm_client=llm,
        mcp_client_factory=lambda: _FakeMcpClient(),
        sessions=SessionStore(max_messages=12),
    )

    response = await service.chat(
        ChatRequest(
            session_id="discord:guild:1:channel:2:user:3",
            user_name="Vincent",
            message="Do I have recent MIOs?",
        )
    )

    assert response.reply == "You have 5 recent MIOs."
    assert response.tool_calls[0].name == "get_mio"
    assert service.sessions.get(response.session_id)


async def test_chat_service_can_clear_history() -> None:
    llm = _FakeLlmClient(
        responses=[
            ChatCompletionResult(
                assistant_message={"role": "assistant", "content": "Fresh reply."},
                text="Fresh reply.",
                tool_calls=[],
            )
        ]
    )
    sessions = SessionStore(max_messages=12)
    sessions.set(
        "session-1",
        [{"role": "user", "content": "stale"}],
    )
    service = ChatService(
        config=_config(),
        llm_client=llm,
        mcp_client_factory=lambda: _FakeMcpClient(),
        sessions=sessions,
    )

    response = await service.chat(
        ChatRequest(session_id="session-1", message="new", clear_history=True)
    )

    assert response.reply == "Fresh reply."
    history = service.sessions.get("session-1")
    assert history[0]["content"] == "new"
