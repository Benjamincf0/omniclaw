from __future__ import annotations

import curses
import queue
import textwrap
import threading
import uuid
from dataclasses import dataclass
from typing import Callable

from .config import TuiConfig
from .orchestrator_client import OrchestratorClient


@dataclass(slots=True)
class ChatLine:
    role: str
    content: str


@dataclass(slots=True)
class CommandResult:
    action: str
    value: str | None = None


class TerminalChatApp:
    def __init__(self, config: TuiConfig) -> None:
        self._config = config
        self._client = OrchestratorClient(
            base_url=config.orchestrator_url,
            timeout_seconds=config.http_timeout_seconds,
        )
        self._session_id = config.session_id
        self._provider = config.provider
        self._model = config.model
        self._messages: list[ChatLine] = [
            ChatLine(
                role="system",
                content=(
                    "Connected to the orchestrator. Type a prompt to chat, or use "
                    "/help for commands."
                ),
            )
        ]
        self._draft = ""
        self._pending = False
        self._scroll_offset = 0
        self._events: queue.SimpleQueue[tuple[str, dict[str, str]]] = queue.SimpleQueue()
        self._running = True
        self._cursor_offset = 0

    def run(self) -> None:
        curses.wrapper(self._run)

    def _run(self, screen: curses.window) -> None:
        curses.curs_set(1)
        curses.noecho()
        curses.cbreak()
        screen.keypad(True)
        screen.timeout(100)
        self._run_background_task(self._check_health)

        while self._running:
            self._drain_events()
            self._draw(screen)
            key = screen.getch()
            if key == -1:
                continue
            self._handle_key(key)

    def _handle_key(self, key: int) -> None:
        if key == 3:
            self._running = False
            return
        if key in {curses.KEY_ENTER, 10, 13}:
            self._submit()
            return
        if key in {curses.KEY_BACKSPACE, 127, 8}:
            if self._cursor_offset > 0:
                self._draft = (
                    self._draft[: self._cursor_offset - 1] + self._draft[self._cursor_offset :]
                )
                self._cursor_offset -= 1
            return
        if key == curses.KEY_UP:
            self._scroll_offset += 1
            return
        if key == curses.KEY_DOWN:
            self._scroll_offset = max(0, self._scroll_offset - 1)
            return
        if key == curses.KEY_LEFT:
            self._cursor_offset = max(0, self._cursor_offset - 1)
            return
        if key == curses.KEY_RIGHT:
            self._cursor_offset = min(len(self._draft), self._cursor_offset + 1)
            return
        if key == curses.KEY_HOME:
            self._cursor_offset = 0
            return
        if key == curses.KEY_END:
            self._cursor_offset = len(self._draft)
            return
        if 32 <= key <= 126:
            self._draft = (
                self._draft[: self._cursor_offset]
                + chr(key)
                + self._draft[self._cursor_offset :]
            )
            self._cursor_offset += 1

    def _submit(self) -> None:
        message = self._draft.strip()
        if not message:
            self._draft = ""
            self._cursor_offset = 0
            return
        self._draft = ""
        self._cursor_offset = 0

        if message.startswith("/"):
            self._handle_command(message)
            return
        if self._pending:
            self._append_message("system", "Wait for the current reply before sending another.")
            return

        self._messages.append(ChatLine(role="you", content=message))
        self._pending = True
        self._scroll_offset = 0

        self._run_background_task(self._send_message, message)

    def _send_message(self, message: str) -> None:
        try:
            payload = self._client.chat(
                session_id=self._session_id,
                user_id=self._config.user_id,
                user_name=self._config.user_name,
                message=message,
                provider=self._provider,
                model=self._model,
            )
            reply = str(payload.get("reply", "")).strip() or "I couldn't produce a reply."
            tool_lines: list[str] = []
            raw_tool_calls = payload.get("tool_calls", [])
            if isinstance(raw_tool_calls, list):
                for item in raw_tool_calls:
                    if not isinstance(item, dict):
                        continue
                    name = str(item.get("name", "tool")).strip() or "tool"
                    arguments = item.get("arguments", {})
                    if isinstance(arguments, dict) and arguments:
                        pairs = ", ".join(
                            f"{key}={value!r}" for key, value in sorted(arguments.items())
                        )
                        tool_lines.append(f"{name}({pairs})")
                    else:
                        tool_lines.append(name)
            self._events.put(
                (
                    "chat_reply",
                    {
                        "reply": reply,
                        "provider": str(payload.get("provider", "")).strip(),
                        "model": str(payload.get("model", "")).strip(),
                        "tools": "\n".join(tool_lines),
                    },
                )
            )
        except Exception as exc:
            self._events.put(("error", {"message": f"{exc}"}))

    def _drain_events(self) -> None:
        while True:
            try:
                event_name, payload = self._events.get_nowait()
            except queue.Empty:
                break
            if event_name == "chat_reply":
                self._pending = False
                reply = payload.get("reply", "")
                if reply:
                    self._append_message("assistant", reply)
                provider = payload.get("provider", "")
                model = payload.get("model", "")
                if provider:
                    self._provider = provider
                if model:
                    self._model = model
                tools = payload.get("tools", "")
                if tools:
                    self._append_message("tools", tools)
                continue
            if event_name == "error":
                self._pending = False
                self._append_message("error", payload.get("message", "Unknown error"))
                continue
            if event_name == "status":
                self._append_message("system", payload.get("message", ""))
                continue
            if event_name == "reset":
                self._messages = [
                    ChatLine(
                        role="system",
                        content=payload.get("message", "Cleared the current session."),
                    )
                ]
                self._scroll_offset = 0
                continue

    def _draw(self, screen: curses.window) -> None:
        screen.erase()
        height, width = screen.getmaxyx()
        transcript_height = max(1, height - 4)

        header = " Omniclaw TUI "
        status = "thinking..." if self._pending else "ready"
        provider_model = self._provider or "default"
        if self._model:
            provider_model = f"{provider_model}/{self._model}"
        subtitle = f"{provider_model} | {status} | Ctrl+C quit"
        self._safe_addnstr(screen, 0, 0, header.ljust(width), width, curses.A_REVERSE)
        if width > len(header) + 1:
            self._safe_addnstr(
                screen,
                0,
                len(header),
                subtitle.rjust(width - len(header)),
                width - len(header),
                curses.A_REVERSE,
            )
        footer = f" session: {self._session_id} "
        self._safe_addnstr(screen, 1, 0, footer.ljust(width), width, curses.A_DIM)

        wrapped_lines: list[tuple[str, str]] = []
        body_width = max(10, width - 2)
        for message in self._messages:
            prefix = f"{message.role}: "
            chunks = textwrap.wrap(
                message.content,
                width=max(8, body_width - len(prefix)),
                replace_whitespace=False,
                drop_whitespace=False,
            ) or [""]
            for index, chunk in enumerate(chunks):
                line_prefix = prefix if index == 0 else " " * len(prefix)
                wrapped_lines.append((message.role, f"{line_prefix}{chunk}".rstrip()))
            wrapped_lines.append((message.role, ""))

        visible_lines = transcript_height - 1
        max_scroll = max(0, len(wrapped_lines) - visible_lines)
        scroll = min(self._scroll_offset, max_scroll)
        start = max(0, len(wrapped_lines) - visible_lines - scroll)
        end = start + visible_lines

        for row, (role, line) in enumerate(wrapped_lines[start:end], start=2):
            style = curses.A_NORMAL
            if role == "system":
                style = curses.A_DIM
            elif role == "error":
                style = curses.A_BOLD
            elif role == "tools":
                style = curses.A_DIM
            self._safe_addnstr(screen, row, 0, line.ljust(width), width, style)

        prompt = f"> {self._draft}"
        help_line = "/help /reset /status /provider <name> /model <name> /session new /quit"
        self._safe_addnstr(screen, height - 2, 0, help_line.ljust(width), width, curses.A_DIM)
        self._safe_addnstr(screen, height - 1, 0, prompt.ljust(width), width, curses.A_BOLD)
        cursor_x = min(width - 1, 2 + self._cursor_offset)
        try:
            screen.move(height - 1, cursor_x)
        except curses.error:
            pass
        screen.refresh()

    def _handle_command(self, raw_command: str) -> None:
        result = self._parse_command(raw_command)
        if result.action == "quit":
            self._running = False
            return
        if result.action == "help":
            self._append_message(
                "system",
                (
                    "Commands:\n"
                    "/help shows this message.\n"
                    "/status checks the orchestrator health endpoint.\n"
                    "/reset clears the current orchestrator session and transcript.\n"
                    "/provider <name> sets a provider override.\n"
                    "/model <name> sets a model override.\n"
                    "/provider default clears the provider override.\n"
                    "/model default clears the model override.\n"
                    "/session new starts a fresh local session id.\n"
                    "/quit exits the TUI."
                ),
            )
            return
        if result.action == "status":
            if self._pending:
                self._append_message("system", "Wait for the current reply before requesting status.")
                return
            self._run_background_task(self._check_health)
            return
        if result.action == "reset":
            if self._pending:
                self._append_message("system", "Wait for the current reply before resetting.")
                return
            self._run_background_task(self._reset_session)
            return
        if result.action == "set_provider":
            self._provider = result.value
            label = self._provider or "default"
            self._append_message("system", f"Provider override: {label}")
            return
        if result.action == "set_model":
            self._model = result.value
            label = self._model or "default"
            self._append_message("system", f"Model override: {label}")
            return
        if result.action == "new_session":
            self._session_id = result.value or self._session_id
            self._messages = [
                ChatLine(
                    role="system",
                    content=f"Started a new local session: {self._session_id}",
                )
            ]
            self._append_message("system", "The previous remote history is still available by its old id.")
            return
        self._append_message("error", f"Unknown command: {raw_command}")

    def _parse_command(self, raw_command: str) -> CommandResult:
        parts = raw_command.strip().split(maxsplit=1)
        command = parts[0].lower()
        argument = parts[1].strip() if len(parts) > 1 else ""

        if command in {"/quit", "/exit"}:
            return CommandResult(action="quit")
        if command == "/help":
            return CommandResult(action="help")
        if command == "/status":
            return CommandResult(action="status")
        if command == "/reset":
            return CommandResult(action="reset")
        if command == "/provider":
            if not argument or argument.lower() == "default":
                return CommandResult(action="set_provider", value=None)
            return CommandResult(action="set_provider", value=argument)
        if command == "/model":
            if not argument or argument.lower() == "default":
                return CommandResult(action="set_model", value=None)
            return CommandResult(action="set_model", value=argument)
        if command == "/session" and argument.lower() == "new":
            return CommandResult(action="new_session", value=self._new_session_id())
        return CommandResult(action="unknown")

    def _check_health(self) -> None:
        try:
            payload = self._client.health()
            servers = payload.get("mcp_servers", [])
            providers = payload.get("available_providers", [])
            message = (
                f"Orchestrator status: {payload.get('status', 'unknown')} | "
                f"default: {payload.get('default_provider', 'unknown')}/"
                f"{payload.get('default_model', 'unknown')} | "
                f"providers: {self._join_values(providers)} | "
                f"MCP servers: {self._join_values(servers)}"
            )
            self._events.put(("status", {"message": message}))
        except Exception as exc:
            self._events.put(("status", {"message": f"Health check failed: {exc}"}))

    def _reset_session(self) -> None:
        try:
            payload = self._client.clear_session(self._session_id)
            remote_session = str(payload.get("session_id", self._session_id))
            self._events.put(
                (
                    "reset",
                    {
                        "message": (
                            "Cleared orchestrator history for session "
                            f"{remote_session}."
                        )
                    },
                )
            )
        except Exception as exc:
            self._events.put(("status", {"message": f"Could not clear the session: {exc}"}))

    def _append_message(self, role: str, content: str) -> None:
        if not content.strip():
            return
        self._messages.append(ChatLine(role=role, content=content.strip()))
        self._scroll_offset = 0

    def _new_session_id(self) -> str:
        prefix = self._config.user_name.replace(" ", "-") or "terminal-user"
        return f"tui:{prefix}:{uuid.uuid4().hex[:8]}"

    def _run_background_task(self, target: Callable[..., None], *args: object) -> None:
        worker = threading.Thread(target=target, args=args, daemon=True)
        worker.start()

    def _join_values(self, values: object) -> str:
        if not isinstance(values, list):
            return "none"
        rendered = ", ".join(str(item) for item in values if str(item).strip())
        return rendered or "none"

    def _safe_addnstr(
        self,
        screen: curses.window,
        y: int,
        x: int,
        text: str,
        width: int,
        attr: int = 0,
    ) -> None:
        try:
            screen.addnstr(y, x, text, width, attr)
        except curses.error:
            return


def run_app(config: TuiConfig) -> None:
    app = TerminalChatApp(config)
    app.run()
