from __future__ import annotations

from typing import Any, Iterable

import discord
from discord import app_commands

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
        self.tree = app_commands.CommandTree(self)
        self._register_commands()

    async def close(self) -> None:
        await self._orchestrator.close()
        await super().close()

    async def setup_hook(self) -> None:
        await self._sync_commands()

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

        async with message.channel.typing():
            try:
                reply = await self._fetch_reply(
                    session_id=self._build_message_session_id(message),
                    user_id=str(message.author.id),
                    user_name=message.author.display_name,
                    prompt=prompt,
                )
            except Exception as exc:
                reply = f"Orchestrator error: {exc}"

        for chunk in _split_reply(reply, self._config.reply_char_limit):
            await message.reply(chunk, mention_author=False)

    def _register_commands(self) -> None:
        @self.tree.command(name="ask", description="Ask Omniclaw a question")
        @app_commands.describe(
            prompt="What you want Omniclaw to help with",
            provider="Optional model provider override",
            model="Optional model override for the selected provider",
        )
        @app_commands.choices(
            provider=[
                app_commands.Choice(name="OpenAI", value="openai"),
                app_commands.Choice(name="Ollama", value="ollama"),
                app_commands.Choice(name="Claude", value="claude"),
                app_commands.Choice(name="Gemini", value="gemini"),
            ]
        )
        async def ask(
            interaction: discord.Interaction,
            prompt: str,
            provider: app_commands.Choice[str] | None = None,
            model: str | None = None,
        ) -> None:
            await interaction.response.defer(thinking=True)
            try:
                reply = await self._fetch_reply(
                    session_id=self._build_interaction_session_id(interaction),
                    user_id=str(interaction.user.id),
                    user_name=interaction.user.display_name,
                    prompt=prompt,
                    provider=provider.value if provider else None,
                    model=model,
                )
            except Exception as exc:
                reply = f"Orchestrator error: {exc}"
            await self._send_followup_chunks(interaction, reply)

        @self.tree.command(
            name="reset",
            description="Clear your Omniclaw conversation in this channel",
        )
        async def reset(interaction: discord.Interaction) -> None:
            await interaction.response.defer(ephemeral=True, thinking=True)
            session_id = self._build_interaction_session_id(interaction)
            try:
                await self._orchestrator.clear_session(session_id)
                reply = "Cleared your Omniclaw session for this channel."
            except Exception as exc:
                reply = f"Could not clear the session: {exc}"
            await self._send_followup_chunks(interaction, reply, ephemeral=True)

        @self.tree.command(
            name="status",
            description="Check whether the bot can reach the orchestrator",
        )
        async def status(interaction: discord.Interaction) -> None:
            await interaction.response.defer(ephemeral=True, thinking=True)
            try:
                payload = await self._orchestrator.health()
                mcp_servers = payload.get("mcp_servers", [])
                if not isinstance(mcp_servers, list):
                    mcp_servers = []
                servers = ", ".join(str(server) for server in mcp_servers) or "none"
                providers = payload.get("available_providers", [])
                if not isinstance(providers, list):
                    providers = []
                provider_text = ", ".join(str(provider) for provider in providers) or "none"
                reply = (
                    "Bot is up.\n"
                    f"Orchestrator status: {payload.get('status', 'unknown')}\n"
                    f"Default model: {payload.get('default_provider', 'unknown')}/"
                    f"{payload.get('default_model', 'unknown')}\n"
                    f"Available providers: {provider_text}\n"
                    f"MCP servers: {servers}"
                )
            except Exception as exc:
                reply = f"Bot is up, but the orchestrator health check failed: {exc}"
            await self._send_followup_chunks(interaction, reply, ephemeral=True)

        @self.tree.command(name="help", description="Show the Omniclaw bot commands")
        async def help_command(interaction: discord.Interaction) -> None:
            channel_mode = "mention the bot" if self._config.require_mention else "message normally"
            reply = (
                "Available commands:\n"
                "/ask <prompt> to talk to Omniclaw in this channel.\n"
                "/ask <prompt> provider:<provider> model:<model> to override the model.\n"
                "/reset to clear your current channel session.\n"
                "/status to check bot and orchestrator connectivity.\n"
                "/help to show this message.\n\n"
                f"Message behavior: in servers, {channel_mode} unless the channel is auto-reply enabled."
            )
            await interaction.response.send_message(reply, ephemeral=True)

    async def _sync_commands(self) -> None:
        guild_ids = sorted(self._config.command_guild_ids)
        if guild_ids:
            for guild_id in guild_ids:
                guild = discord.Object(id=guild_id)
                self.tree.copy_global_to(guild=guild)
                try:
                    synced = await self.tree.sync(guild=guild)
                except Exception as exc:
                    print(f"Failed to sync commands to guild {guild_id}: {exc}")
                    continue
                print(f"Synced {len(synced)} commands to guild {guild_id}")
            return

        try:
            synced = await self.tree.sync()
        except Exception as exc:
            print(f"Failed to sync global commands: {exc}")
            return
        print(f"Synced {len(synced)} global commands")

    async def _fetch_reply(
        self,
        *,
        session_id: str,
        user_id: str,
        user_name: str,
        prompt: str,
        provider: str | None = None,
        model: str | None = None,
    ) -> str:
        payload = await self._orchestrator.chat(
            session_id=session_id,
            user_id=user_id,
            user_name=user_name,
            message=prompt,
            provider=provider,
            model=model,
        )
        reply = str(payload.get("reply", "")).strip()
        if not reply:
            return "I couldn't produce a reply."
        return reply

    async def _send_followup_chunks(
        self,
        interaction: discord.Interaction,
        text: str,
        *,
        ephemeral: bool = False,
    ) -> None:
        chunks = _split_reply(text, self._config.reply_char_limit)
        if not chunks:
            chunks = ["I couldn't produce a reply."]
        for chunk in chunks:
            await interaction.followup.send(chunk, ephemeral=ephemeral)

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

    def _build_message_session_id(self, message: discord.Message) -> str:
        if message.guild is None:
            return f"discord:dm:channel:{message.channel.id}:user:{message.author.id}"
        return (
            "discord:"
            f"guild:{message.guild.id}:"
            f"channel:{message.channel.id}:"
            f"user:{message.author.id}"
        )

    def _build_interaction_session_id(self, interaction: discord.Interaction[Any]) -> str:
        if interaction.channel_id is None:
            return f"discord:user:{interaction.user.id}"
        if interaction.guild_id is None:
            return f"discord:dm:channel:{interaction.channel_id}:user:{interaction.user.id}"
        return (
            "discord:"
            f"guild:{interaction.guild_id}:"
            f"channel:{interaction.channel_id}:"
            f"user:{interaction.user.id}"
        )
