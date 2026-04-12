from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable
from uuid import uuid4

from .config import AppConfig
from .contracts import ChatRequest, ChatResponse, ToolCallRecord
from .llm import OpenAICompatibleChatClient
from .mcp_client import MultiServerMcpClient


class SessionStore:
    def __init__(self, max_messages: int) -> None:
        self._max_messages = max_messages
        self._sessions: dict[str, list[dict[str, Any]]] = {}

    def get(self, session_id: str) -> list[dict[str, Any]]:
        return [message.copy() for message in self._sessions.get(session_id, [])]

    def set(self, session_id: str, messages: list[dict[str, Any]]) -> None:
        self._sessions[session_id] = [message.copy() for message in messages[-self._max_messages :]]

    def clear(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)


@dataclass(slots=True)
class ChatService:
    config: AppConfig
    llm_client: OpenAICompatibleChatClient
    mcp_client_factory: Callable[[], MultiServerMcpClient]
    sessions: SessionStore

    @classmethod
    def from_config(cls, config: AppConfig) -> ChatService:
        llm_client = OpenAICompatibleChatClient(
            api_key=config.openai_api_key,
            base_url=config.openai_base_url,
            model=config.openai_model,
            temperature=config.openai_temperature,
        )
        return cls(
            config=config,
            llm_client=llm_client,
            mcp_client_factory=lambda: MultiServerMcpClient(config.mcp_servers),
            sessions=SessionStore(config.history_limit),
        )

    async def chat(self, request: ChatRequest) -> ChatResponse:
        message_text = request.message.strip()
        if not message_text:
            raise ValueError("message must not be empty")

        session_id = request.session_id or f"session-{uuid4()}"
        if request.clear_history:
            self.sessions.clear(session_id)

        history = self.sessions.get(session_id)
        user_message = self._build_user_message(request, message_text)
        conversation: list[dict[str, Any]] = [
            {"role": "system", "content": self.config.system_prompt},
            *history,
            user_message,
        ]
        tool_call_records: list[ToolCallRecord] = []

        async with self.mcp_client_factory() as mcp_client:
            tools = await mcp_client.get_openai_tools()

            for _ in range(self.config.max_tool_rounds):
                completion = await self.llm_client.complete(
                    messages=conversation,
                    tools=tools,
                )
                conversation.append(completion.assistant_message)

                if completion.tool_calls:
                    for tool_call in completion.tool_calls:
                        tool_call_records.append(
                            ToolCallRecord(
                                name=tool_call.name,
                                arguments=tool_call.arguments,
                            )
                        )
                        tool_output = await self._call_tool_safely(
                            mcp_client=mcp_client,
                            name=tool_call.name,
                            arguments=tool_call.arguments,
                        )
                        conversation.append(
                            {
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "name": tool_call.name,
                                "content": tool_output,
                            }
                        )
                    continue

                reply = completion.text.strip()
                if not reply:
                    reply = "I couldn't produce a reply for that request."

                self.sessions.set(session_id, conversation[1:])
                return ChatResponse(
                    session_id=session_id,
                    reply=reply,
                    tool_calls=tool_call_records,
                )

        raise RuntimeError("The model exceeded the maximum number of tool rounds")

    def clear_session(self, session_id: str) -> None:
        self.sessions.clear(session_id)

    def _build_user_message(
        self, request: ChatRequest, message_text: str
    ) -> dict[str, str]:
        if request.user_name:
            content = f"User: {request.user_name}\nMessage: {message_text}"
        else:
            content = message_text
        return {"role": "user", "content": content}

    async def _call_tool_safely(
        self,
        *,
        mcp_client: MultiServerMcpClient,
        name: str,
        arguments: dict[str, Any],
    ) -> str:
        try:
            return await mcp_client.call_tool(name, arguments)
        except Exception as exc:
            return json.dumps(
                {
                    "is_error": True,
                    "error": str(exc),
                    "content": [],
                },
                ensure_ascii=True,
                indent=2,
            )
