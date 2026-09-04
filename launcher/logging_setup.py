"""File logging for the launcher process.

Everything goes to ``%LOCALAPPDATA%\\Dobby\\logs\\launcher.log`` with
timestamps. ``--console`` additionally mirrors to stderr for diagnostics.

The server subprocess does NOT use this module — its stdout/stderr are
redirected to ``server.log`` by :class:`launcher.server.ServerProcess`.
"""

import logging
import sys

from . import paths

_FORMAT = "%(asctime)s %(levelname)-7s [%(name)s] %(message)s"
_configured = False


def setup_logging(console: bool = False) -> logging.Logger:
    """Configure root logging to launcher.log (and optionally stderr)."""
    global _configured
    root = logging.getLogger()
    if not _configured:
        paths.ensure_dirs()
        root.setLevel(logging.INFO)
        formatter = logging.Formatter(_FORMAT)

        file_handler = logging.FileHandler(paths.LAUNCHER_LOG, encoding="utf-8")
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

        if console:
            stream_handler = logging.StreamHandler(sys.stderr)
            stream_handler.setFormatter(formatter)
            root.addHandler(stream_handler)

        _configured = True
    return logging.getLogger("launcher")
