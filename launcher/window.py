"""pywebview native window for Dobby OS.

pywebview requires the GUI loop on the MAIN thread on Windows —
:meth:`DobbyWindow.start` blocks there until the window is destroyed.
``destroy()`` and ``show()`` are safe to call from other threads (tray /
timer threads); pywebview marshals them internally.

Closing the window HIDES it (the app lives in the tray); only an explicit
``destroy()`` (tray Quit) ends the GUI loop.
"""

import logging

import webview

from . import paths

log = logging.getLogger("launcher.window")

WINDOW_TITLE = "Dobby OS"
WINDOW_WIDTH = 1440
WINDOW_HEIGHT = 900


class DobbyWindow:
    def __init__(self) -> None:
        self._window = None
        self._allow_close = False

    def create(self):
        self._window = webview.create_window(
            WINDOW_TITLE,
            paths.SERVER_URL,
            width=WINDOW_WIDTH,
            height=WINDOW_HEIGHT,
            resizable=True,
        )
        self._window.events.closing += self._on_closing
        log.info("window created: title=%r url=%s size=%dx%d resizable=True",
                 WINDOW_TITLE, paths.SERVER_URL, WINDOW_WIDTH, WINDOW_HEIGHT)
        return self._window

    def _on_closing(self):
        """Returning False cancels the close; we hide instead (tray app)."""
        if self._allow_close:
            log.info("window closing (quit in progress)")
            return True
        log.info("window close intercepted -> hide (app stays in tray)")
        try:
            self._window.hide()
        except Exception:
            log.exception("window hide failed")
        return False

    def show(self):
        """Show/focus the window (tray 'Open'). Thread-safe."""
        log.info("window show/focus requested")
        if self._window is None:
            return
        try:
            self._window.show()
            self._window.restore()
        except Exception:
            log.exception("window show failed")

    def destroy(self):
        """End the GUI loop (tray 'Quit'). Thread-safe in pywebview."""
        if self._window is None:
            return
        self._allow_close = True
        log.info("window destroy requested")
        try:
            self._window.destroy()
        except Exception:
            log.exception("window destroy failed")

    def start(self):
        """Run the GUI loop on the calling (MAIN) thread; blocks until
        the window is destroyed."""
        log.info("webview loop starting (main thread)")
        webview.start(
            private_mode=False,
            storage_path=str(paths.WEBVIEW_DIR),
        )
        log.info("webview loop exited")
