"""App orchestration: paths -> server -> ollama -> window -> tray.

Quit path (tray Quit, and --smoke's programmatic trigger — SAME code):
    App.quit() -> window.destroy() -> [main thread: webview loop exits]
    -> server.stop() (terminate, 5s grace, kill) -> tray.stop() -> exit.

Restart server (tray): stop + start the subprocess WITHOUT touching the
window.
"""

import ctypes
import logging
import os
import sys
import threading

from . import paths
from .ollama_check import OllamaStatus, check_and_start
from .server import ServerProcess
from .tray import Tray
from .window import DobbyWindow

log = logging.getLogger("launcher.app")

_MB_ICONWARNING = 0x00000030
_MB_SETFOREGROUND = 0x00010000


def show_dialog(title: str, message: str, block: bool = False) -> None:
    """Native MessageBox. Non-blocking by default (daemon thread)."""
    log.info("dialog: title=%r message=%r block=%s", title, message, block)
    if os.name != "nt":
        return

    def _show() -> None:
        ctypes.windll.user32.MessageBoxW(
            None, message, title, _MB_ICONWARNING | _MB_SETFOREGROUND)

    if block:
        _show()
    else:
        threading.Thread(target=_show, name="dialog", daemon=True).start()


class App:
    def __init__(self, smoke: float | None = None,
                 smoke_restart: bool = False) -> None:
        self.smoke = smoke
        self.smoke_restart = smoke_restart
        self.server = ServerProcess()
        self.window = DobbyWindow()
        self.tray: Tray | None = None
        self._quitting = threading.Event()

    # ----- tray callbacks (fire on the tray / timer thread) -----

    def open_window(self) -> None:
        log.info("tray: Open")
        self.window.show()

    def restart_server(self) -> None:
        log.info("tray: Restart server")
        ok = self.server.restart()
        if not ok:
            log.error("server restart failed; last %d lines of server.log:\n%s",
                      50, self.server.tail_server_log())
            show_dialog(
                "Dobby OS",
                f"The Dobby server failed to restart.\nSee {paths.LAUNCHER_LOG}",
                block=False,
            )

    def quit(self) -> None:
        """The tray-Quit code path (also triggered programmatically by
        --smoke). Only destroys the window here; the main thread finishes
        the shutdown once the webview loop returns."""
        if self._quitting.is_set():
            return
        self._quitting.set()
        log.info("quit: destroying window (shutdown continues on main thread)")
        self.window.destroy()

    # ----- smoke automation -----

    def _smoke_quit(self) -> None:
        log.info("smoke: %.0fs elapsed -> triggering the tray-Quit code path",
                 self.smoke)
        self.quit()

    def _smoke_restart(self) -> None:
        log.info("smoke: exercising the tray Restart-server handler")
        self.restart_server()

    # ----- main flow -----

    def run(self) -> int:
        paths.ensure_dirs()
        log.info("launcher starting: python=%s frozen=%s home=%s pid=%s",
                 sys.version.split()[0], paths.is_frozen(), paths.DOBBY_HOME,
                 os.getpid())

        self.server.start()
        if not self.server.wait_healthy():
            log.error("server failed to become healthy; last 50 lines of "
                      "server.log:\n%s", self.server.tail_server_log())
            self.server.stop()
            show_dialog(
                "Dobby OS",
                f"The Dobby server failed to start.\nSee {paths.LAUNCHER_LOG}",
                block=self.smoke is None,  # never block smoke automation
            )
            return 1

        ollama = check_and_start()
        log.info("ollama status: %s", ollama.name)
        if ollama is OllamaStatus.NOT_INSTALLED:
            show_dialog(
                "Dobby OS",
                "Ollama not found — install from https://ollama.com",
                block=False,
            )

        try:
            self.window.create()
            self.tray = Tray(on_open=self.open_window,
                             on_restart=self.restart_server,
                             on_quit=self.quit)
            self.tray.start()

            if self.smoke is not None:
                log.info("smoke mode: auto-quit in %.0fs (restart check: %s)",
                         self.smoke, self.smoke_restart)
                quit_timer = threading.Timer(self.smoke, self._smoke_quit)
                quit_timer.daemon = True
                quit_timer.start()
                if self.smoke_restart:
                    restart_timer = threading.Timer(
                        max(3.0, self.smoke / 3), self._smoke_restart)
                    restart_timer.daemon = True
                    restart_timer.start()

            self.window.start()  # blocks the main thread until destroy()
        finally:
            # Runs on normal quit AND if the GUI layer throws — the server
            # subprocess must never be orphaned.
            log.info("shutdown: webview loop exited; stopping server")
            self.server.stop()
            if self.tray is not None:
                self.tray.stop()
        log.info("shutdown complete: exiting 0")
        return 0
