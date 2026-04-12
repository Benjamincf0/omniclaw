from __future__ import annotations

import curses
import queue
import textwrap
import threading
from dataclasses import dataclass

from .config import TuiConfig
from .orchestrator_client import OrchestratorClient


@dataclass(slots=True)
class ChatLine:
    role: str
    content: str


class TerminalChatApp:
    def __init__(self, config: TuiConfig) -> None:
        self._config = config
        self._client = OrchestratorClient(
            base_url=config.orchestrator_url,
            timeout_seconds=config.http_timeout_seconds,
        )
        self._messages: list[ChatLine] = []
        self._draft = ""
        self._pending = False
        self._scroll_offset = 0
        self._events: queue.SimpleQueue[tuple[str, str]] = queue.SimpleQueue()
        self._running = True

    def run(self) -> None:
        curses.wrapper(self._run)

    def _run(self, screen: curses.window) -> None:
        curses.curs_set(1)
        curses.noecho()
        curses.cbreak()
        screen.keypad(True)
        screen.timeout(100)

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
            self._draft = self._draft[:-1]
            return
        if key == curses.KEY_UP:
            self._scroll_offset += 1
            return
        if key == curses.KEY_DOWN:
            self._scroll_offset = max(0, self._scroll_offset - 1)
            return
        if 32 <= key <= 126:
            self._draft += chr(key)

    def _submit(self) -> None:
        message = self._draft.strip()
        if self._pending or not message:
            self._draft = ""
            return

        self._messages.append(ChatLine(role="you", content=message))
        self._draft = ""
        self._pending = True
        self._scroll_offset = 0

        worker = threading.Thread(
            target=self._send_message,
            args=(message,),
            daemon=True,
        )
        worker.start()

    def _send_message(self, message: str) -> None:
        try:
            payload = self._client.chat(
                session_id=self._config.session_id,
                user_id=self._config.user_id,
                user_name=self._config.user_name,
                message=message,
                provider=self._config.provider,
                model=self._config.model,
            )
            reply = str(payload.get("reply", "")).strip() or "I couldn't produce a reply."
            self._events.put(("assistant", reply))
        except Exception as exc:
            self._events.put(("error", f"{exc}"))

    def _drain_events(self) -> None:
        while True:
            try:
                role, content = self._events.get_nowait()
            except queue.Empty:
                break
            self._pending = False
            self._messages.append(ChatLine(role=role, content=content))

    def _draw(self, screen: curses.window) -> None:
        screen.erase()
        height, width = screen.getmaxyx()
        transcript_height = max(1, height - 3)

        header = " Omniclaw TUI "
        status = "thinking..." if self._pending else "ready"
        provider_model = self._config.provider or "default"
        if self._config.model:
            provider_model = f"{provider_model}/{self._config.model}"
        subtitle = f"{provider_model} | {status} | Ctrl+C quit"
        screen.addnstr(0, 0, header.ljust(width), width, curses.A_REVERSE)
        if width > len(header) + 1:
            screen.addnstr(0, len(header), subtitle.rjust(width - len(header)), width - len(header))

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

        for row, (_, line) in enumerate(wrapped_lines[start:end], start=1):
            screen.addnstr(row, 0, line.ljust(width), width)

        prompt = f"> {self._draft}"
        screen.addnstr(height - 1, 0, prompt.ljust(width), width, curses.A_BOLD)
        cursor_x = min(width - 1, len(prompt))
        screen.move(height - 1, cursor_x)
        screen.refresh()


def run_app(config: TuiConfig) -> None:
    app = TerminalChatApp(config)
    app.run()
