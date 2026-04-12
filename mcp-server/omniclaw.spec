# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for Omniclaw desktop build.

Build with:  pyinstaller omniclaw.spec
Output:      dist/omniclaw/omniclaw.exe
"""

import os

block_cipher = None

a = Analysis(
    ["launcher.py"],
    pathex=[],
    binaries=[],
    datas=[
        ("static", "static"),
        ("models", "models"),
        ("auth.txt", "."),
        (".env", "."),
    ],
    hiddenimports=[
        # uvicorn dynamically imports these
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
        # app modules
        "omni",
        "omnivox_client",
        "auth_manager",
        "models",
        "models.mio",
        "models.news",
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
    ],
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
