from __future__ import annotations

import json
from contextlib import AsyncExitStack
from dataclasses import dataclass
from typing import Any

from mcp import ClientSession, types
from mcp.client.streamable_http import streamablehttp_client

from .config import McpServerConfig


@dataclass(slots=True)
class ExposedTool:
    name: str
    description: str
    input_schema: dict[str, Any]
    server_name: str
    remote_name: str

    def as_openai_tool(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_schema,
            },
        }

    def as_anthropic_tool(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }

    def as_gemini_function_declaration(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.input_schema,
        }


@dataclass(slots=True)
class _ServerConnection:
    config: McpServerConfig
    session: ClientSession


def _serialize_tool_result(result: types.CallToolResult) -> str:
    serialized_content: list[dict[str, Any]] = []
    for item in result.content:
        if isinstance(item, types.TextContent):
            serialized_content.append({"type": "text", "text": item.text})
        elif isinstance(item, types.ImageContent):
            serialized_content.append(
                {
                    "type": "image",
                    "mime_type": item.mimeType,
                    "data": "[base64 image omitted]",
                }
            )
        elif isinstance(item, types.EmbeddedResource):
            resource = item.resource
            if hasattr(resource, "model_dump"):
                resource_payload = resource.model_dump(mode="json", by_alias=True)
            else:
                resource_payload = str(resource)
            serialized_content.append(
                {"type": "resource", "resource": resource_payload}
            )
        else:
            if hasattr(item, "model_dump"):
                payload = item.model_dump(mode="json", by_alias=True)
            else:
                payload = str(item)
            serialized_content.append({"type": "unknown", "value": payload})

    payload = {
        "is_error": bool(result.isError),
        "structured_content": result.structuredContent,
        "content": serialized_content,
    }
    return json.dumps(payload, ensure_ascii=True, indent=2, default=str)


class MultiServerMcpClient:
    def __init__(self, server_configs: list[McpServerConfig]) -> None:
        self._server_configs = server_configs
        self._connections: dict[str, _ServerConnection] = {}
        self._tools_by_name: dict[str, ExposedTool] = {}
        self._exit_stack = AsyncExitStack()

    async def __aenter__(self) -> MultiServerMcpClient:
        for config in self._server_configs:
            headers: dict[str, str] | None = None
            if config.bearer_token:
                headers = {"Authorization": f"Bearer {config.bearer_token}"}

            read_stream, write_stream, _ = await self._exit_stack.enter_async_context(
                streamablehttp_client(config.url, headers=headers)
            )
            session = ClientSession(read_stream, write_stream)
            await self._exit_stack.enter_async_context(session)
            await session.initialize()
            self._connections[config.name] = _ServerConnection(config=config, session=session)
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        await self._exit_stack.aclose()

    async def list_tools(self) -> list[ExposedTool]:
        if self._tools_by_name:
            return list(self._tools_by_name.values())

        use_prefixes = len(self._connections) > 1
        for server_name, connection in self._connections.items():
            result = await connection.session.list_tools()
            for tool in result.tools:
                exposed_name = (
                    f"{server_name}__{tool.name}" if use_prefixes else tool.name
                )
                if exposed_name in self._tools_by_name:
                    raise ValueError(f"Duplicate tool name exposed: {exposed_name}")
                self._tools_by_name[exposed_name] = ExposedTool(
                    name=exposed_name,
                    description=tool.description or f"{server_name}::{tool.name}",
                    input_schema=tool.inputSchema or {"type": "object", "properties": {}},
                    server_name=server_name,
                    remote_name=tool.name,
                )

        return list(self._tools_by_name.values())

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        if not self._tools_by_name:
            await self.list_tools()
        tool = self._tools_by_name.get(name)
        if tool is None:
            raise ValueError(f"Unknown MCP tool: {name}")
        # Strip any arguments the LLM hallucinated that aren't in the tool schema.
        known_params = set(tool.input_schema.get("properties", {}).keys())
        if known_params:
            arguments = {k: v for k, v in arguments.items() if k in known_params}
        connection = self._connections[tool.server_name]
        result = await connection.session.call_tool(tool.remote_name, arguments)
        return _serialize_tool_result(result)
