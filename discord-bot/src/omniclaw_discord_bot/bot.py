from __future__ import annotations

from typing import Iterable

import discord

from .config import DiscordBotConfig
from .orchestrator_client import OrchestratorClient


def _split_reply(text: str, limit: int) -> list[str]:
    cleaned = text.strip()
    if not cleaned:
        return []

    chunks: list[str] = []
    remaining = cleaned
    while len(remaining) > limit:
        split_at = remaining.rfind("\n", 0, limit)
        if split_at == -1:
            split_at = remaining.rfind(" ", 0, limit)
        if split_at == -1:
            split_at = limit
        chunk = remaining[:split_at].strip()
        if not chunk:
            chunk = remaining[:limit].strip()
            split_at = limit
        chunks.append(chunk)
        remaining = remaining[split_at:].strip()
    if remaining:
        chunks.append(remaining)
    return chunks


class OmniclawDiscordBot(discord.Client):
    def __init__(self, config: DiscordBotConfig) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.messages = True

        super().__init__(intents=intents)
        self._config = config
        self._orchestrator = OrchestratorClient(
            base_url=config.orchestrator_url,
            timeout_seconds=config.http_timeout_seconds,
        )

    async def close(self) -> None:
        await self._orchestrator.close()
        await super().close()

    async def on_ready(self) -> None:
        if self.user is None:
            return
        print(f"Logged in as {self.user} (id={self.user.id})")

    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return
        if self.user is None:
            return
        if not self._should_respond(message):
            return

        prompt = self._extract_prompt(message)
        if not prompt:
            return

        session_id = self._build_session_id(message)
        async with message.channel.typing():
            try:
                payload = await self._orchestrator.chat(
                    session_id=session_id,
                    user_id=str(message.author.id),
                    user_name=message.author.display_name,
                    message=prompt,
                )
                reply = str(payload.get("reply", "")).strip()
                if not reply:
                    reply = "I couldn't produce a reply."
            except Exception as exc:
                reply = f"Orchestrator error: {exc}"

        for chunk in _split_reply(reply, self._config.reply_char_limit):
            await message.reply(chunk, mention_author=False)

    def _should_respond(self, message: discord.Message) -> bool:
        if message.guild is None:
            return self._config.allow_dms
        if message.channel.id in self._config.auto_reply_channel_ids:
            return True
        if self._config.require_mention:
            return self.user in message.mentions
        return True

    def _extract_prompt(self, message: discord.Message) -> str:
        content = message.content.strip()
        if self.user is None:
            return content

        mention_tokens = self._mention_tokens()
        for token in mention_tokens:
            content = content.replace(token, " ")
        return " ".join(content.split())

    def _mention_tokens(self) -> Iterable[str]:
        if self.user is None:
            return []
        return (f"<@{self.user.id}>", f"<@!{self.user.id}>")

    def _build_session_id(self, message: discord.Message) -> str:
        if message.guild is None:
            return f"discord:dm:channel:{message.channel.id}:user:{message.author.id}"
        return (
            "discord:"
            f"guild:{message.guild.id}:"
            f"channel:{message.channel.id}:"
            f"user:{message.author.id}"
        )
