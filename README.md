# Dobby Desktop

## What this is

Windows desktop packaging for Dobby OS — a PyInstaller onedir exe that launches the Dobby OS server on 127.0.0.1:7001 and opens it in a native pywebview window with a pystray tray icon. Ollama is an external prerequisite, never bundled.

## Relationship

Dobby OS lives at [github.com/xicoocosta/dobby](https://github.com/xicoocosta/dobby), consumed here as a pinned git submodule at `vendor/dobby`. Dobby is itself a fork of upstream Odysseus.

## License

AGPL-3.0-or-later, as a derivative of AGPL Odysseus/Dobby. The complete corresponding source is this repository plus the pinned submodule commit.

## Build instructions

_[completed in Phase 5]_

## Data directory

All runtime data lives under `%LOCALAPPDATA%\Dobby`; the install folder stays clean.

## Packaging caveats

- **Unsigned executable.** `DobbyOS.exe` is not code-signed, so Windows SmartScreen will show an "unrecognized app" warning on first run (More info → Run anyway), and some antivirus engines may false-positive on a PyInstaller-built exe. Mitigations: the build is onedir (not onefile), which already reduces AV heuristic flags; if your AV still flags it, add an exclusion for the install folder. Code signing is the real fix and is planned for a later release.
- **Firewall prompt on first launch.** The server binds `127.0.0.1:7001` (loopback only). Windows Firewall may still ask for permission on first launch — allowing it does not expose anything to the network or the internet; there is no inbound internet exposure.
- **The `DobbyOS/` folder must stay intact.** This is a onedir bundle: `DobbyOS.exe` needs the `_internal/` folder next to it (the dobby application tree ships inside it and is resolved via the launcher's base-dir probe). Move, copy, or zip the whole `DobbyOS/` folder — never the exe alone.
- **Optional features disabled or degraded in v1:**
  - Built-in MCP servers are disabled (`ODYSSEUS_DISABLE_MCP=1`). The four server scripts ship on disk under `_internal/dobby/mcp_servers/` for a future re-enable.
  - Runtime pip installs and the agent's Python tool don't work from a frozen exe (there is no pip inside the bundle) — a frozen-exe limitation.
  - `requirements-optional.txt` extras are not bundled: local speech-to-text (faster-whisper), DuckDuckGo search provider (ddgs), PDF form-filling (PyMuPDF), AI background removal (rembg), AI upscale (realesrgan), browser automation (playwright), and Office/EPUB extraction (markitdown). The app degrades gracefully where these are missing, but they cannot be pip-installed into the frozen bundle.
