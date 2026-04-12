"""
Omniclaw Desktop Launcher

Loads the shared .env, starts Ollama (if installed), launches the MCP server,
orchestrator, and Discord bot in parallel, and opens the default browser.
This replicates the behaviour of ``./omniclaw up`` inside a single process so
the PyInstaller bundle can ship everything as one executable.
"""

import os
import sys
import signal
import socket
import shutil
import subprocess
import threading
import time
import webbrowser
from pathlib import Path

from config_paths import user_config_file

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8000
ORCHESTRATOR_HOST = "127.0.0.1"
ORCHESTRATOR_PORT = 8080
OLLAMA_HOST = "127.0.0.1"
OLLAMA_PORT = 11434
BROWSER_DELAY = 2.0


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent


def _user_config_path() -> Path:
    """Writable env file (Application Support when frozen, repo .env when dev)."""
    return user_config_file()


def _load_env_file(env_file: Path, *, override: bool = False) -> None:
    if not env_file.exists():
        return
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        key, sep, value = line.partition("=")
        if not sep:
            continue
        key = key.strip()
        if not key:
            continue
        if not override and key in os.environ:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ[key] = value


def _load_env() -> None:
    _load_env_file(_user_config_path(), override=True)
    if getattr(sys, "frozen", False):
        legacy = Path(sys.executable).parent / "omniclaw.env"
        _load_env_file(legacy, override=False)
    _load_env_file(_base_dir() / ".env", override=False)


def _set_defaults() -> None:
    os.environ.setdefault("MCP_HOST", SERVER_HOST)
    os.environ.setdefault("MCP_PORT", str(SERVER_PORT))
    os.environ.setdefault("MCP_TRANSPORT_PATH", "/mcp")
    os.environ.setdefault("ORCHESTRATOR_HOST", ORCHESTRATOR_HOST)
    os.environ.setdefault("ORCHESTRATOR_PORT", str(ORCHESTRATOR_PORT))
    os.environ.setdefault("OMNICLAW_ENV_FILE", str(_user_config_path()))
    if getattr(sys, "frozen", False):
        os.environ.setdefault("OMNICLAW_START_WITHOUT_API_KEYS", "1")

    if not os.environ.get("ORCHESTRATOR_URL", "").strip():
        port = os.environ["ORCHESTRATOR_PORT"]
        os.environ["ORCHESTRATOR_URL"] = f"http://127.0.0.1:{port}"

    if not os.environ.get("MCP_SERVER_URLS", "").strip():
        transport = "/" + os.environ["MCP_TRANSPORT_PATH"].strip().strip("/")
        transport = transport.rstrip("/") or "/mcp"
        mcp_port = os.environ["MCP_PORT"]
        os.environ["MCP_SERVER_URLS"] = (
            f"omnivox=http://127.0.0.1:{mcp_port}{transport}"
        )


# -- Ollama helpers ----------------------------------------------------------

def _is_port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        try:
            s.connect((host, port))
            return True
        except (ConnectionRefusedError, TimeoutError, OSError):
            return False


def _find_ollama() -> str | None:
    found = shutil.which("ollama")
    if found:
        return found
    common_paths = [
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Ollama\ollama.exe"),
        os.path.expandvars(r"%PROGRAMFILES%\Ollama\ollama.exe"),
    ]
    if sys.platform == "darwin":
        common_paths.extend(
            [
                "/Applications/Ollama.app/Contents/Resources/ollama",
                os.path.expanduser(
                    "~/Applications/Ollama.app/Contents/Resources/ollama"
                ),
            ]
        )
    for p in common_paths:
        if os.path.isfile(p):
            return p
    return None


def _start_ollama() -> subprocess.Popen | None:
    ollama = _find_ollama()
    if not ollama:
        print("[launcher] Ollama not found — skipping (install it for local models)")
        return None

    if _is_port_open(OLLAMA_HOST, OLLAMA_PORT):
        print("[launcher] Ollama already running")
        return None

    print(f"[launcher] Starting Ollama from {ollama} ...")
    proc = subprocess.Popen(
        [ollama, "serve"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )

    for _ in range(30):
        if _is_port_open(OLLAMA_HOST, OLLAMA_PORT):
            print("[launcher] Ollama is ready")
            return proc
        time.sleep(0.5)

    print("[launcher] Ollama started but port not open yet — continuing anyway")
    return proc


# -- Service runners (each blocks its own thread) ----------------------------

def _run_mcp_server() -> None:
    try:
        from omni import main as start_server
        start_server()
    except Exception as exc:
        print(f"[launcher] MCP server stopped: {exc}")


def _run_orchestrator() -> None:
    try:
        import uvicorn
        from omniclaw_orchestrator.server import app as orch_app

        cfg = orch_app.state.config
        uvicorn.run(orch_app, host=cfg.host, port=cfg.port, reload=False)
    except ValueError as exc:
        print(f"[launcher] Orchestrator skipped (config incomplete): {exc}")
    except Exception as exc:
        print(f"[launcher] Orchestrator stopped: {exc}")


def _run_discord_bot() -> None:
    token = os.environ.get("DISCORD_BOT_TOKEN", "").strip()
    if not token:
        print("[launcher] DISCORD_BOT_TOKEN not set — skipping Discord bot")
        return
    try:
        from omniclaw_discord_bot.main import main as start_bot
        start_bot()
    except Exception as exc:
        print(f"[launcher] Discord bot stopped: {exc}")


def _open_browser_delayed() -> None:
    for _ in range(60):
        if _is_port_open(SERVER_HOST, SERVER_PORT):
            time.sleep(BROWSER_DELAY)
            url = f"http://{SERVER_HOST}:{SERVER_PORT}"
            print(f"[launcher] Opening {url}")
            webbrowser.open(url)
            return
        time.sleep(0.5)
    print("[launcher] Server did not start in time — open http://localhost:8000 manually")


# -- Entry point -------------------------------------------------------------

def main():
    print("=" * 50)
    print("  Omniclaw — Desktop Launcher")
    print("=" * 50)
    print()

    _load_env()
    _set_defaults()

    ollama_proc = _start_ollama()

    services = [
        ("MCP server", _run_mcp_server),
        ("Orchestrator", _run_orchestrator),
        ("Discord bot", _run_discord_bot),
    ]

    threads: list[tuple[str, threading.Thread]] = []
    for name, target in services:
        t = threading.Thread(target=target, name=name, daemon=True)
        t.start()
        threads.append((name, t))
        print(f"[launcher] Started {name}")

    browser_thread = threading.Thread(target=_open_browser_delayed, daemon=True)
    browser_thread.start()

    print("[launcher] All services starting. Press Ctrl+C to stop.")

    try:
        while any(t.is_alive() for _, t in threads):
            time.sleep(0.5)
        print("[launcher] All services have stopped.")
    except KeyboardInterrupt:
        print("\n[launcher] Shutting down ...")
    finally:
        if ollama_proc:
            print("[launcher] Stopping Ollama ...")
            ollama_proc.terminate()
            try:
                ollama_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                ollama_proc.kill()
        print("[launcher] Goodbye!")


if __name__ == "__main__":
    main()
