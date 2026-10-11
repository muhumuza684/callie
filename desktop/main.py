"""Callie desktop app. Double-click: Callie starts inside this program and opens in its own window.
Your data (key, contacts, memory, logs) lives in your user folder, never next to the program."""
import os
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

DEFAULT_PORT = 8731


def app_home() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home())
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return base / "Callie"


def browser_candidates() -> list:
    found = []
    if sys.platform == "win32":
        for var in ("ProgramFiles(x86)", "ProgramFiles", "LOCALAPPDATA"):
            base = os.environ.get(var)
            if base:
                found += [Path(base) / "Microsoft/Edge/Application/msedge.exe", Path(base) / "Google/Chrome/Application/chrome.exe"]
    elif sys.platform == "darwin":
        found += [Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
                  Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge")]
    else:
        import shutil
        found += [Path(p) for p in (shutil.which(n) for n in ("google-chrome", "chromium", "chromium-browser", "microsoft-edge")) if p]
    return found


def open_window(url: str):
    """An app-style window (no address bar) in Edge or Chrome; the normal browser if neither is installed."""
    if os.environ.get("CALLIE_NO_WINDOW"):
        return
    for exe in browser_candidates():
        if exe.exists():
            try:
                subprocess.Popen([str(exe), f"--app={url}", "--window-size=1100,780"])
                return
            except OSError:
                continue
    webbrowser.open(url)


def healthy(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1.5) as r:
            return r.status == 200
    except Exception:
        return False


def free_port(preferred: int) -> int:
    import socket
    for p in (preferred, 0):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", p))
                return s.getsockname()[1]
            except OSError:
                continue
    return preferred


def run():
    home = app_home()
    home.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("CALLIE_HOME", str(home))
    port = int(os.environ.get("CALLIE_PORT", DEFAULT_PORT))
    if healthy(port):                          # already running: just open another window
        open_window(f"http://127.0.0.1:{port}/")
        return
    for name in ("stdout", "stderr"):          # a windowed program has no console to print to
        if getattr(sys, name) is None:
            setattr(sys, name, open(os.devnull, "w"))
    port = free_port(port)

    import uvicorn
    from server import config
    from server import main as srv             # imported only now, after CALLIE_HOME is set

    server = uvicorn.Server(uvicorn.Config(srv.app, host="127.0.0.1", port=port, log_config=None))
    threading.Thread(target=server.run, daemon=True).start()
    for _ in range(100):
        if healthy(port):
            break
        time.sleep(0.2)
    else:
        return
    open_window(f"http://127.0.0.1:{port}/" + ("" if config.GROQ_API_KEY else "setup"))

    idle = float(os.environ.get("CALLIE_IDLE_SECONDS", 180))      # window closed for this long -> Callie quits
    first = float(os.environ.get("CALLIE_FIRST_SECONDS", 300))    # nobody ever opened it -> quit
    start = time.monotonic()
    while not server.should_exit:
        time.sleep(2)
        last = srv.STATE["ping"]
        quiet = time.monotonic() - (last or start)
        if quiet > (idle if last else first):
            server.should_exit = True
    time.sleep(1)


if __name__ == "__main__":
    run()
