# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for Omniclaw desktop build.

Bundles the MCP server, orchestrator, and Discord bot into a single
executable that mirrors ``./omniclaw up``.

Build with:  pyinstaller omniclaw.spec
Output:      dist/omniclaw/omniclaw(.exe on Windows)
"""

import os
import sys
from PyInstaller.utils.hooks import collect_all, collect_submodules

# UPX breaks or complicates many macOS bundles and Gatekeeper workflows.
_USE_UPX = sys.platform != "darwin"


def _collect(pkg):
    """collect_all but silently skip packages not installed in this env."""
    try:
        d, b, h = collect_all(pkg)
        return d, b, h
    except Exception:
        return [], [], []


def _playwright_driver_datas():
    """
    Playwright ships a native driver binary inside the package that PyInstaller's
    collect_all misses.  Locate it and add it to datas so the subprocess can find
    it at runtime inside the bundle.
    """
    try:
        import playwright
        pkg_dir = os.path.dirname(playwright.__file__)
        driver_dir = os.path.join(pkg_dir, "driver")
        if os.path.isdir(driver_dir):
            return [(driver_dir, os.path.join("playwright", "driver"))]
    except Exception:
        pass
    return []


block_cipher = None

# Run collect_all for every package listed in pyproject.toml that has
# dynamic imports.  This is more robust than maintaining a manual list of
# submodules because it mirrors exactly what uv installed in the venv.
_packages = [
    "fastmcp",
    "mcp",
    "google.genai",
    "google.ai.generativelanguage",
    "discord",
    "playwright",
    "fastapi",
    "starlette",
    "uvicorn",
    "httpx",
    "anyio",
    "pydantic",
    "aiohttp",
    "bs4",
    "dotenv",
]

_all_datas, _all_bins, _all_imports = [], [], []
for _pkg in _packages:
    _d, _b, _h = _collect(_pkg)
    _all_datas  += _d
    _all_bins   += _b
    _all_imports += _h

try:
    _spec_root = os.path.dirname(os.path.abspath(SPECPATH))
except NameError:
    _spec_root = os.getcwd()
_optional_secrets = []
for _fn in ("auth.txt", ".env"):
    if os.path.isfile(os.path.join(_spec_root, _fn)):
        _optional_secrets.append((_fn, "."))

a = Analysis(
    ["launcher.py"],
    pathex=[
        os.path.abspath(os.path.join("..", "orchestrator")),
        os.path.abspath(os.path.join("..", "discord-bot", "src")),
    ],
    binaries=_all_bins,
    datas=[
        ("static", "static"),
        ("models", "models"),
        (os.path.join("..", "orchestrator", "omniclaw_orchestrator"),
         "omniclaw_orchestrator"),
        (os.path.join("..", "discord-bot", "src", "omniclaw_discord_bot"),
         "omniclaw_discord_bot"),
    ] + _optional_secrets + _all_datas + _playwright_driver_datas(),
    hiddenimports=[
        # local app modules (not auto-discoverable by static analysis)
        "omni",
        "omnivox_client",
        "auth_manager",
        "models",
        "models.mio",
        "models.news",
        "omniclaw_orchestrator",
        "omniclaw_orchestrator.main",
        "omniclaw_orchestrator.config",
        "omniclaw_orchestrator.contracts",
        "omniclaw_orchestrator.llm",
        "omniclaw_orchestrator.mcp_client",
        "omniclaw_orchestrator.server",
        "omniclaw_orchestrator.service",
        "omniclaw_discord_bot",
        "omniclaw_discord_bot.main",
        "omniclaw_discord_bot.config",
        "omniclaw_discord_bot.bot",
        "omniclaw_discord_bot.orchestrator_client",
        # small leaf modules that static analysis still misses
        "sniffio",
        "h11",
    ] + _all_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Only exclude packages that are genuinely not needed at runtime
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
    upx=_USE_UPX,
    console=True,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=_USE_UPX,
    upx_exclude=[],
    name="omniclaw",
)
