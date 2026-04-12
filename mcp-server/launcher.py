"""
Omniclaw Desktop Launcher

Starts Ollama (if installed and not already running), launches the FastAPI
backend server, and opens the user's default browser.
"""

import os
import sys
import socket
import shutil
import subprocess
import threading
import time
import webbrowser

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8000
OLLAMA_HOST = "127.0.0.1"
OLLAMA_PORT = 11434
BROWSER_DELAY = 2.0


def _is_port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        try:
            s.connect((host, port))
            return True
        except (ConnectionRefusedError, TimeoutError, OSError):
            return False


def _find_ollama() -> str | None:
    """Return the path to the ollama executable, or None."""
    found = shutil.which("ollama")
    if found:
        return found
    common_paths = [
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Ollama\ollama.exe"),
        os.path.expandvars(r"%PROGRAMFILES%\Ollama\ollama.exe"),
    ]
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


def _open_browser_delayed():
    """Wait for the server to become ready, then open the browser."""
    for _ in range(60):
        if _is_port_open(SERVER_HOST, SERVER_PORT):
            time.sleep(BROWSER_DELAY)
            url = f"http://{SERVER_HOST}:{SERVER_PORT}"
            print(f"[launcher] Opening {url}")
            webbrowser.open(url)
            return
        time.sleep(0.5)
    print("[launcher] Server did not start in time — open http://localhost:8000 manually")


def main():
    print("=" * 50)
    print("  Omniclaw — Desktop Launcher")
    print("=" * 50)
    print()

    ollama_proc = _start_ollama()

    browser_thread = threading.Thread(target=_open_browser_delayed, daemon=True)
    browser_thread.start()

    try:
        from omni import main as start_server
        start_server()
    except KeyboardInterrupt:
        print("\n[launcher] Shutting down ...")
    finally:
        if ollama_proc:
            print("[launcher] Stopping Ollama ...")
            ollama_proc.terminate()
            ollama_proc.wait(timeout=5)
        print("[launcher] Goodbye!")


if __name__ == "__main__":
    main()
