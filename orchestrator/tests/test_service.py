from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from omniclaw_orchestrator.config import AppConfig, McpServerConfig, ModelProviderConfig
from omniclaw_orchestrator.contracts import ChatRequest
from omniclaw_orchestrator.llm import ChatCompletionResult, ResolvedChatClient, ToolCall
from omniclaw_orchestrator.mcp_client import ExposedTool
from omniclaw_orchestrator.service import ChatService, SessionStore


@dataclass
class _FakeLlmClient:
    responses: list[ChatCompletionResult]
    last_messages: list[dict[str, Any]] | None = None
    last_tools: list[ExposedTool] | None = None

    async def complete(
        self, *, messages: list[dict[str, Any]], tools: list[ExposedTool]
    ) -> ChatCompletionResult:
        assert tools
        self.last_messages = messages
        self.last_tools = tools
        return self.responses.pop(0)


@dataclass
class _FakeLlmRegistry:
    provider: str
    model: str
    client: _FakeLlmClient

    @property
    def default_provider(self) -> str:
        return self.provider

    def default_model(self) -> str:
        return self.model

    def available_providers(self) -> list[str]:
        return [self.provider]

    def resolve(
        self, *, provider: str | None = None, model: str | None = None
    ) -> ResolvedChatClient:
        return ResolvedChatClient(
            provider=provider or self.provider,
            model=model or self.model,
            client=self.client,
        )


class _FakeMcpClient:
    async def __aenter__(self) -> _FakeMcpClient:
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        return None

    async def list_tools(self) -> list[ExposedTool]:
        return [
            ExposedTool(
                name="get_mio",
                description="Fetch MIOs",
                input_schema={"type": "object", "properties": {}},
                server_name="omnivox",
                remote_name="get_mio",
            )
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        assert name == "get_mio"
        assert arguments == {"num": 5}
        return '{"is_error": false, "content": [{"type": "text", "text": "5 MIOs"}]}'


def _config() -> AppConfig:
    return AppConfig(
        host="127.0.0.1",
        port=8080,
        default_model_provider="openai",
        model_providers={
            "openai": ModelProviderConfig(
                provider="openai",
                api_key="test-key",
                base_url="https://example.com/v1",
                default_model="test-model",
                temperature=0.2,
                max_output_tokens=1024,
            )
        },
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
        llm_registry=_FakeLlmRegistry(provider="claude", model="claude-3-7-sonnet", client=llm),
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
    assert response.provider == "claude"
    assert response.model == "claude-3-7-sonnet"
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
        llm_registry=_FakeLlmRegistry(provider="openai", model="gpt-5.4-mini", client=llm),
        mcp_client_factory=lambda: _FakeMcpClient(),
        sessions=sessions,
    )

    response = await service.chat(
        ChatRequest(session_id="session-1", message="new", clear_history=True)
    )

    assert response.reply == "Fresh reply."
    assert response.provider == "openai"
    assert response.model == "gpt-5.4-mini"
    history = service.sessions.get("session-1")
    assert history[0]["content"] == "new"


async def test_chat_service_allows_request_level_provider_and_model_override() -> None:
    llm = _FakeLlmClient(
        responses=[
            ChatCompletionResult(
                assistant_message={"role": "assistant", "content": "Gemini reply."},
                text="Gemini reply.",
                tool_calls=[],
            )
        ]
    )
    service = ChatService(
        config=_config(),
        llm_registry=_FakeLlmRegistry(provider="openai", model="gpt-5.4-mini", client=llm),
        mcp_client_factory=lambda: _FakeMcpClient(),
        sessions=SessionStore(max_messages=12),
    )

    response = await service.chat(
        ChatRequest(
            session_id="session-2",
            message="try gemini",
            provider="gemini",
            model="gemini-2.5-pro",
        )
    )

    assert response.reply == "Gemini reply."
    assert response.provider == "gemini"
    assert response.model == "gemini-2.5-pro"


async def test_chat_service_adds_orchestration_guidance_to_system_messages() -> None:
    llm = _FakeLlmClient(
        responses=[
            ChatCompletionResult(
                assistant_message={"role": "assistant", "content": "Assignments reply."},
                text="Assignments reply.",
                tool_calls=[],
            )
        ]
    )

    class _AssignmentsMcpClient(_FakeMcpClient):
        async def list_tools(self) -> list[ExposedTool]:
            return [
                ExposedTool(
                    name="get_lea_classes",
                    description="Get classes",
                    input_schema={"type": "object", "properties": {}},
                    server_name="omnivox",
                    remote_name="get_lea_classes",
                ),
                ExposedTool(
                    name="get_lea_assignments",
                    description="Get assignments",
                    input_schema={
                        "type": "object",
                        "properties": {"link": {"type": "string"}},
                    },
                    server_name="omnivox",
                    remote_name="get_lea_assignments",
                ),
            ]

    service = ChatService(
        config=_config(),
        llm_registry=_FakeLlmRegistry(provider="openai", model="gpt-5.4-mini", client=llm),
        mcp_client_factory=lambda: _AssignmentsMcpClient(),
        sessions=SessionStore(max_messages=12),
    )

    response = await service.chat(
        ChatRequest(session_id="session-3", message="What are all my assignments?")
    )

    assert response.reply == "Assignments reply."
    assert llm.last_messages is not None
    system_messages = [
        str(message["content"])
        for message in llm.last_messages
        if message.get("role") == "system"
    ]
    assert any("Infer and execute prerequisite tool calls yourself" in msg for msg in system_messages)
    assert any("LEA assignments workflow: call get_lea_classes first" in msg for msg in system_messages)
