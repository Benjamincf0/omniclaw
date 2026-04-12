from __future__ import annotations

import unittest

from omniclaw_tui.app import TerminalChatApp
from omniclaw_tui.config import TuiConfig


def _config() -> TuiConfig:
    return TuiConfig(
        orchestrator_url="http://127.0.0.1:8080",
        session_id="tui:test:abcd1234",
        user_id="vincent",
        user_name="Vincent",
        provider=None,
        model=None,
        http_timeout_seconds=90,
    )


class TerminalChatAppTests(unittest.TestCase):
    def test_parse_provider_override(self) -> None:
        app = TerminalChatApp(_config())

        result = app._parse_command("/provider gemini")

        self.assertEqual(result.action, "set_provider")
        self.assertEqual(result.value, "gemini")

    def test_parse_default_model_override(self) -> None:
        app = TerminalChatApp(_config())

        result = app._parse_command("/model default")

        self.assertEqual(result.action, "set_model")
        self.assertIsNone(result.value)

    def test_parse_new_session_command(self) -> None:
        app = TerminalChatApp(_config())

        result = app._parse_command("/session new")

        self.assertEqual(result.action, "new_session")
        self.assertIsNotNone(result.value)
        assert result.value is not None
        self.assertTrue(result.value.startswith("tui:Vincent:"))


if __name__ == "__main__":
    unittest.main()
