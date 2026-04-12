from __future__ import annotations

from .bot import OmniclawDiscordBot
from .config import load_config


def main() -> None:
    config = load_config()
    bot = OmniclawDiscordBot(config)
    bot.run(config.token)
