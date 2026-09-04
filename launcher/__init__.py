"""Dobby OS desktop launcher.

Runs the dobby FastAPI server as a subprocess (this same program in a
``--serve`` role), shows the UI in a native pywebview window, and lives in
the system tray. Closing the window hides it; the tray menu offers
Open / Restart server / Quit.

Entry point: ``python -m launcher`` (dev) or the frozen exe (Phase 4).
"""

__version__ = "0.1.0"
