"""Server subprocess management (launcher role) and the server role itself.

Launcher role — :class:`ServerProcess` spawns THIS SAME PROGRAM with
``--serve``:

    dev:    [sys.executable, "-m", "launcher", "--serve"]
    frozen: [sys.executable, "--serve"]

so exactly one code path runs the server in dev and in the frozen exe.

Server role — :func:`serve` chdirs into the dobby base dir (app.py mounts
``static`` relative to CWD), puts it on sys.path, guarantees the data dir
exists BEFORE importing dobby's ``app`` (core/database.py connects at
import), and runs uvicorn in-process on 127.0.0.1:7001.
"""

import logging
import os
import subprocess
import sys
import time
from pathlib import Path

import requests

from . import paths

log = logging.getLogger("launcher.server")

HEALTH_POLL_INTERVAL_S = 0.5
HEALTH_TIMEOUT_S = 30.0
STOP_GRACE_S = 5.0
LOG_TAIL_LINES = 50


def build_server_env() -> dict:
    """Environment for the server subprocess (gate-approved v1 contract)."""
    env = dict(os.environ)
    env["ODYSSEUS_DATA_DIR"] = str(paths.DATA_DIR)
    # APP_PORT is used by dobby for internal loopback self-calls; it MUST
    # match the uvicorn port (src/constants.py:103).
    env["APP_PORT"] = str(paths.SERVER_PORT)
    # Built-in MCP servers are spawned by dobby as
    # `<ODYSSEUS_MCP_PYTHON> <script_path>` (src/builtin_mcp.py). The frozen
    # exe has python-like script semantics (SCRIPT role in __main__.py), so
    # it can BE that interpreter. Dev mode needs no override: sys.executable
    # is a real python there and dobby falls back to it.
    if getattr(sys, "frozen", False):
        env["ODYSSEUS_MCP_PYTHON"] = sys.executable
    # Line-buffer the redirected stdout/stderr so server.log fills promptly.
    env["PYTHONUNBUFFERED"] = "1"
    return env


def spawn_command() -> list:
    if paths.is_frozen():
        return [sys.executable, "--serve"]
    return [sys.executable, "-m", "launcher", "--serve"]


class ServerProcess:
    """Owns the dobby server subprocess: spawn, health poll, stop, restart."""

    def __init__(self) -> None:
        self.proc: subprocess.Popen | None = None
        self._log_handle = None

    @property
    def pid(self):
        return self.proc.pid if self.proc else None

    def start(self) -> None:
        paths.ensure_dirs()
        cmd = spawn_command()
        env = build_server_env()
        if paths.is_frozen():
            cwd = str(Path(sys.executable).resolve().parent)
        else:
            # `python -m launcher` resolves the package via CWD=repo root.
            cwd = str(paths.repo_root())
        self._log_handle = open(paths.SERVER_LOG, "ab")
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        self.proc = subprocess.Popen(
            cmd,
            cwd=cwd,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=self._log_handle,
            stderr=subprocess.STDOUT,
            creationflags=creationflags,
        )
        log.info(
            "server spawn: cmd=%s cwd=%s pid=%s (stdout/stderr -> %s)",
            cmd, cwd, self.proc.pid, paths.SERVER_LOG,
        )

    def wait_healthy(self) -> bool:
        """Poll GET /api/health every 500ms for up to 30s."""
        log.info("health poll: GET %s every %.1fs, timeout %.0fs",
                 paths.HEALTH_URL, HEALTH_POLL_INTERVAL_S, HEALTH_TIMEOUT_S)
        deadline = time.monotonic() + HEALTH_TIMEOUT_S
        while time.monotonic() < deadline:
            if self.proc is not None and self.proc.poll() is not None:
                log.error("server exited during startup: pid=%s exitcode=%s",
                          self.proc.pid, self.proc.returncode)
                return False
            try:
                resp = requests.get(paths.HEALTH_URL, timeout=2)
                if resp.status_code == 200:
                    log.info("health OK: GET %s -> %s", paths.HEALTH_URL,
                             resp.status_code)
                    return True
            except requests.RequestException:
                pass
            time.sleep(HEALTH_POLL_INTERVAL_S)
        log.error("health poll timed out after %.0fs", HEALTH_TIMEOUT_S)
        return False

    def tail_server_log(self, lines: int = LOG_TAIL_LINES) -> str:
        """Last N lines of server.log (for failure reports in launcher.log)."""
        try:
            text = paths.SERVER_LOG.read_text(encoding="utf-8", errors="replace")
            return "\n".join(text.splitlines()[-lines:])
        except OSError as exc:
            return f"<could not read {paths.SERVER_LOG}: {exc}>"

    def stop(self) -> None:
        """terminate(), 5s grace, then kill(). Zero orphans."""
        if self.proc is None:
            return
        pid = self.proc.pid
        if self.proc.poll() is None:
            log.info("server stop: terminate() pid=%s", pid)
            self.proc.terminate()
            try:
                self.proc.wait(timeout=STOP_GRACE_S)
            except subprocess.TimeoutExpired:
                log.warning("server still alive after %.0fs grace, kill() pid=%s",
                            STOP_GRACE_S, pid)
                self.proc.kill()
                self.proc.wait(timeout=10)
        log.info("server exit: pid=%s exitcode=%s", pid, self.proc.returncode)
        self.proc = None
        if self._log_handle is not None:
            self._log_handle.close()
            self._log_handle = None

    def restart(self) -> bool:
        """Stop + start the subprocess (window untouched); True when healthy."""
        old_pid = self.pid
        log.info("server restart requested (old pid=%s)", old_pid)
        self.stop()
        self.start()
        healthy = self.wait_healthy()
        log.info("server restart result: old_pid=%s new_pid=%s healthy=%s",
                 old_pid, self.pid, healthy)
        return healthy


def serve() -> None:
    """The SERVER role (invoked with --serve). Runs uvicorn in-process."""
    base = paths.dobby_base_dir()
    # StaticFiles(directory="static") in dobby's app.py is CWD-relative.
    os.chdir(base)
    sys.path.insert(0, str(base))

    # Defaults only — the launcher parent sets these explicitly. (No MCP
    # disable here: built-in MCP is live; the parent wires
    # ODYSSEUS_MCP_PYTHON when frozen — see build_server_env.)
    os.environ.setdefault("ODYSSEUS_DATA_DIR", str(paths.DATA_DIR))
    os.environ.setdefault("APP_PORT", str(paths.SERVER_PORT))

    # The data dir is NOT auto-created and core/database.py connects at
    # import time — create it before dobby's app module is imported.
    os.makedirs(os.environ["ODYSSEUS_DATA_DIR"], exist_ok=True)

    # Root handler so app/uvicorn loggers land on stderr, which the parent
    # redirects into server.log (uvicorn.run below uses log_config=None).
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stderr,
        format="%(asctime)s %(levelname)-7s [%(name)s] %(message)s",
    )
    print(f"[launcher --serve] base={base} data={os.environ['ODYSSEUS_DATA_DIR']} "
          f"port={paths.SERVER_PORT} python={sys.version.split()[0]}", flush=True)

    import uvicorn
    import app as dobby_app  # dobby's app.py, resolved via sys.path[0] = base

    uvicorn.run(dobby_app.app, host=paths.SERVER_HOST, port=paths.SERVER_PORT,
                log_config=None)
