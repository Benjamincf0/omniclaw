from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from omniclaw_tui.config import load_config


class LoadConfigTests(unittest.TestCase):
    def test_explicit_environment_values_are_used(self) -> None:
        values = {
            "ORCHESTRATOR_URL": "http://localhost:9090/",
            "TUI_SESSION_ID": "tui:test:session-1",
            "TUI_USER_ID": "user-123",
            "TUI_USER_NAME": "Vincent",
            "TUI_PROVIDER": "openai",
            "TUI_MODEL": "gpt-5.4-mini",
            "TUI_HTTP_TIMEOUT_SECONDS": "12.5",
        }

        with patch.dict(os.environ, values, clear=True):
            config = load_config()

        self.assertEqual(config.orchestrator_url, "http://localhost:9090")
        self.assertEqual(config.session_id, "tui:test:session-1")
        self.assertEqual(config.user_id, "user-123")
        self.assertEqual(config.user_name, "Vincent")
        self.assertEqual(config.provider, "openai")
        self.assertEqual(config.model, "gpt-5.4-mini")
        self.assertEqual(config.http_timeout_seconds, 12.5)

    def test_defaults_fill_missing_values(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            config = load_config()

        self.assertEqual(config.orchestrator_url, "http://127.0.0.1:8080")
        self.assertEqual(config.user_id, config.user_name)
        self.assertIsNone(config.provider)
        self.assertIsNone(config.model)
        self.assertGreater(config.http_timeout_seconds, 0)
        self.assertTrue(config.session_id.startswith("tui:"))


if __name__ == "__main__":
    unittest.main()
