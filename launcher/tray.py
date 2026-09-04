"""System tray icon (pystray) with menu: Open / Restart server / Quit.

No .ico asset exists in the repo, so the glyph is generated at runtime with
Pillow: a dark disc with a light "D".

pystray runs detached (its own thread); menu callbacks therefore fire on
the tray thread. The App wires them so that Quit only calls the (thread-
safe) window destroy — the main thread performs the actual shutdown after
the webview loop exits.
"""

import logging
import threading

import pystray
from PIL import Image, ImageDraw, ImageFont

log = logging.getLogger("launcher.tray")

ICON_SIZE = 64


def _make_icon_image(size: int = ICON_SIZE) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse((2, 2, size - 2, size - 2),
                 fill=(30, 30, 46, 255), outline=(137, 180, 250, 255), width=3)
    try:
        font = ImageFont.load_default(size=int(size * 0.55))  # Pillow >= 10.1
    except TypeError:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), "D", font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((size - tw) / 2 - bbox[0], (size - th) / 2 - bbox[1]),
              "D", fill=(205, 214, 244, 255), font=font)
    return img


class Tray:
    def __init__(self, on_open, on_restart, on_quit) -> None:
        menu = pystray.Menu(
            pystray.MenuItem("Open", lambda icon, item: on_open(), default=True),
            pystray.MenuItem("Restart server", lambda icon, item: on_restart()),
            pystray.MenuItem("Quit", lambda icon, item: on_quit()),
        )
        self.icon = pystray.Icon("dobby-os", _make_icon_image(), "Dobby OS", menu)

    def start(self) -> None:
        try:
            self.icon.run_detached()
            log.info("tray started (run_detached): menu=Open/Restart server/Quit")
        except NotImplementedError:
            thread = threading.Thread(target=self.icon.run, name="tray", daemon=True)
            thread.start()
            log.info("tray started (daemon thread fallback)")

    def stop(self) -> None:
        log.info("tray stop")
        try:
            self.icon.stop()
        except Exception:
            log.exception("tray stop failed")
