"""Filesystem locations and network constants for the Dobby OS launcher.

All persisted runtime state lives under ``%LOCALAPPDATA%\\Dobby``:

    DOBBY_HOME\\data   -> handed to the server subprocess as ODYSSEUS_DATA_DIR
    DOBBY_HOME\\logs   -> launcher.log (this process) + server.log (subprocess)
    DOBBY_HOME\\webview -> pywebview/WebView2 profile storage

The dobby application base dir (the directory containing dobby's ``app.py``
and ``static/``) is resolved differently in dev vs frozen mode — see
:func:`dobby_base_dir`.
"""

import os
import sys
from pathlib import Path

APP_NAME = "Dobby"

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 7001
SERVER_URL = f"http://{SERVER_HOST}:{SERVER_PORT}"
HEALTH_URL = f"{SERVER_URL}/api/health"

DOBBY_HOME = (
    Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
    / APP_NAME
)
DATA_DIR = DOBBY_HOME / "data"
LOGS_DIR = DOBBY_HOME / "logs"
WEBVIEW_DIR = DOBBY_HOME / "webview"
LAUNCHER_LOG = LOGS_DIR / "launcher.log"
SERVER_LOG = LOGS_DIR / "server.log"


def ensure_dirs() -> None:
    """Create the Dobby home tree. Must run before the server subprocess
    imports dobby's ``app`` (core/database.py connects at import and the
    data dir is NOT auto-created by dobby)."""
    for d in (DOBBY_HOME, DATA_DIR, LOGS_DIR, WEBVIEW_DIR):
        d.mkdir(parents=True, exist_ok=True)


def is_frozen() -> bool:
    """True when running from a PyInstaller (or similar) bundle."""
    return bool(getattr(sys, "frozen", False))


def repo_root() -> Path:
    """Dev-mode repo root (the parent of this ``launcher`` package)."""
    return Path(__file__).resolve().parent.parent


def dobby_base_dir() -> Path:
    """Resolve the dobby application base dir (contains app.py + static/).

    Dev:    <repo>/vendor/dobby
    Frozen: alongside the bundle — ``<exe dir>/dobby`` (preferred layout for
            Phase 4) with fallbacks for ``<exe dir>/vendor/dobby`` and the
            PyInstaller onefile extraction dir (sys._MEIPASS).

    The server subprocess must ``os.chdir`` here before importing dobby's
    ``app``: app.py mounts StaticFiles(directory="static") RELATIVE to CWD.
    """
    if is_frozen():
        exe_dir = Path(sys.executable).resolve().parent
        candidates = [exe_dir / "dobby", exe_dir / "vendor" / "dobby"]
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass) / "dobby")
            candidates.append(Path(meipass) / "vendor" / "dobby")
    else:
        candidates = [repo_root() / "vendor" / "dobby"]

    for cand in candidates:
        if (cand / "app.py").is_file() and (cand / "static").is_dir():
            return cand

    raise FileNotFoundError(
        "Could not locate the dobby base dir (needs app.py + static/). Tried: "
        + ", ".join(str(c) for c in candidates)
    )
