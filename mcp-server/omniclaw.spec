# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for Omniclaw desktop build.

Bundles the MCP server, orchestrator, and Discord bot into a single
executable that mirrors ``./omniclaw up``.

Build with:  pyinstaller omniclaw.spec
Output:      dist/omniclaw/omniclaw.exe
"""

import os
from PyInstaller.utils.hooks import collect_all

block_cipher = None

fastmcp_datas,    fastmcp_bins,    fastmcp_imports    = collect_all("fastmcp")
googlegenai_datas, googlegenai_bins, googlegenai_imports = collect_all("google.genai")
mcp_datas,        mcp_bins,        mcp_imports        = collect_all("mcp")
discord_datas,    discord_bins,    discord_imports    = collect_all("discord")

a = Analysis(
    ["launcher.py"],
    pathex=[
        os.path.abspath(os.path.join("..", "orchestrator", "src")),
        os.path.abspath(os.path.join("..", "discord-bot", "src")),
    ],
    binaries=(
        []
        + fastmcp_bins
        + googlegenai_bins
        + mcp_bins
        + discord_bins
    ),
    datas=[
        ("static", "static"),
        ("models", "models"),
        ("auth.txt", "."),
        (".env", "."),
        # Bundle orchestrator and discord-bot packages so they are importable
        (os.path.join("..", "orchestrator", "src", "omniclaw_orchestrator"),
         "omniclaw_orchestrator"),
        (os.path.join("..", "discord-bot", "src", "omniclaw_discord_bot"),
         "omniclaw_discord_bot"),
    ]
    + fastmcp_datas
    + googlegenai_datas
    + mcp_datas
    + discord_datas,
    hiddenimports=[
        # uvicorn dynamic imports
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.loops.asyncio",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.http.h11_impl",
        "uvicorn.protocols.http.httptools_impl",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.protocols.websockets.wsproto_impl",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        "uvicorn.lifespan.off",
        # MCP server modules
        "omni",
        "omnivox_client",
        "auth_manager",
        "models",
        "models.mio",
        "models.news",
        # Orchestrator modules
        "omniclaw_orchestrator",
        "omniclaw_orchestrator.main",
        "omniclaw_orchestrator.config",
        "omniclaw_orchestrator.contracts",
        "omniclaw_orchestrator.llm",
        "omniclaw_orchestrator.mcp_client",
        "omniclaw_orchestrator.server",
        "omniclaw_orchestrator.service",
        # Discord bot modules
        "omniclaw_discord_bot",
        "omniclaw_discord_bot.main",
        "omniclaw_discord_bot.config",
        "omniclaw_discord_bot.bot",
        "omniclaw_discord_bot.orchestrator_client",
        # discord.py internals
        "discord",
        "discord.ext",
        "discord.ext.commands",
        "discord.ext.tasks",
        # common deps PyInstaller may miss
        "dotenv",
        "httpx",
        "httpx._transports",
        "httpx._transports.default",
        "anyio",
        "anyio._backends",
        "anyio._backends._asyncio",
        "sniffio",
        "h11",
        "pydantic",
        "fastapi",
        "starlette",
        "starlette.routing",
        "starlette.staticfiles",
        "starlette.responses",
        "aiohttp",
    ]
    + fastmcp_imports
    + googlegenai_imports
    + mcp_imports
    + discord_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "playwright",
        "tkinter",
        "matplotlib",
        "scipy",
        "numpy",
        "PIL",
        "IPython",
        "notebook",
        "pytest",
    ],
    noarchive=False,
    optimize=0,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="omniclaw",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="omniclaw",
)
