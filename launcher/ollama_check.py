"""Ollama availability ladder (fixed decision, exact order):

1. GET http://localhost:11434/api/version (2s timeout) -> 200 = RUNNING
2. else, if ``ollama`` is on PATH: spawn ``ollama serve`` detached
   (CREATE_NO_WINDOW | DETACHED_PROCESS), re-poll every 1s up to 15s
   -> STARTED (returned even if unconfirmed within 15s; logged as such —
   the daemon keeps warming up in the background)
3. ``ollama`` not on PATH -> NOT_INSTALLED (caller shows a non-blocking
   dialog; the UI opens anyway and model calls fail gracefully server-side)

The spawned daemon is intentionally detached: it is an external service we
leave running, NOT part of the launcher's process tree.
"""

import enum
import logging
import os
import shutil
import subprocess
import time

import requests

log = logging.getLogger("launcher.ollama")

OLLAMA_VERSION_URL = "http://localhost:11434/api/version"
SPAWN_POLL_INTERVAL_S = 1.0
SPAWN_POLL_TIMEOUT_S = 15.0


class OllamaStatus(enum.Enum):
    RUNNING = "running"
    STARTED = "started"
    NOT_INSTALLED = "not_installed"


def _is_up(timeout: float = 2.0) -> bool:
    try:
        return requests.get(OLLAMA_VERSION_URL, timeout=timeout).status_code == 200
    except requests.RequestException:
        return False


def check_and_start() -> OllamaStatus:
    if _is_up():
        log.info("ollama ladder: GET %s -> 200 => RUNNING", OLLAMA_VERSION_URL)
        return OllamaStatus.RUNNING

    exe = shutil.which("ollama")
    if exe is None:
        log.warning("ollama ladder: 'ollama' not on PATH => NOT_INSTALLED")
        return OllamaStatus.NOT_INSTALLED

    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS
    proc = subprocess.Popen(
        [exe, "serve"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags,
        close_fds=True,
    )
    log.info("ollama ladder: spawned detached: cmd=['%s', 'serve'] pid=%s",
             exe, proc.pid)

    deadline = time.monotonic() + SPAWN_POLL_TIMEOUT_S
    while time.monotonic() < deadline:
        if _is_up(timeout=1.0):
            log.info("ollama ladder: daemon answered after spawn => STARTED")
            return OllamaStatus.STARTED
        time.sleep(SPAWN_POLL_INTERVAL_S)

    log.warning("ollama ladder: spawned pid=%s but no 200 within %.0fs "
                "=> STARTED (unconfirmed; daemon may still be warming up)",
                proc.pid, SPAWN_POLL_TIMEOUT_S)
    return OllamaStatus.STARTED
