# Dobby Desktop

Windows desktop packaging for Dobby OS — a PyInstaller onedir exe (`DobbyOS.exe`) that starts the Dobby OS server on `127.0.0.1:7001` and opens it in a native pywebview window with a pystray tray icon. Dobby OS lives at [github.com/xicoocosta/dobby](https://github.com/xicoocosta/dobby) (itself a fork of upstream Odysseus) and is consumed here as a git submodule pinned at `vendor/dobby`. Ollama is the runtime model backend — an external prerequisite, never bundled.

## Prerequisites

- Windows 10/11
- Python 3.12
- git
- ~2 GB free disk space for the build
- [Ollama](https://ollama.com) as the runtime model backend — installed separately, never bundled (see Ollama below)

## Build

```powershell
git clone --recurse-submodules https://github.com/xicoocosta/dobby-desktop
cd dobby-desktop
powershell -NoProfile -ExecutionPolicy Bypass -File build-windows.ps1
```

If you cloned without `--recurse-submodules`, run `git submodule update --init` first. `vendor/dobby` is pinned to commit `01ce7cda371e9ff3d447d2e646d7fe9bf0a5cfbf` (branch `redesign/baseline`); the build script verifies the pin and aborts if the submodule is at the wrong commit or has a dirty working tree.

The script creates `.venv` if missing (Python 3.12), installs dobby's requirements plus the launcher requirements and `pyinstaller>=6,<7`, runs a PyInstaller onedir build, and zips the result:

- `dist\DobbyOS\` — 2,723 files, 233.6 MB (`DobbyOS.exe` ~29.4 MB)
- `dist\DobbyOS-win64.zip` — 106.6 MB

## Run

Launch `dist\DobbyOS\DobbyOS.exe` (keep the whole `DobbyOS\` folder together — see Packaging caveats). On first launch:

1. SmartScreen shows an "unrecognized app" warning (the exe carries only a self-signed signature — see Packaging caveats) — click **More info → Run anyway**.
2. Windows Firewall may prompt about the server. It binds `127.0.0.1:7001` (loopback only); allowing it exposes nothing to the network or the internet.
3. The server takes ~13 s to come up healthy, then a native "Dobby OS" window (1440x900) opens.
4. Authentication is on by default: the window shows dobby's own first-run account setup / login, where you create your account.

Closing the window hides it — the app keeps running in the tray. The tray menu offers **Open**, **Restart server**, and **Quit**. All data and logs live under `%LOCALAPPDATA%\Dobby` (see Data directory).

## Ollama

At startup the launcher probes for Ollama and takes the first branch that applies (branches 1 and 3 verified on the built exe; branch 2 in dev mode):

1. Daemon already running → used as-is.
2. Installed but not running → auto-started as a detached process.
3. Not installed → a non-blocking dialog points at [https://ollama.com](https://ollama.com), and the UI still opens.

## Data directory

Everything the app persists lives under `%LOCALAPPDATA%\Dobby`:

- `data\` — database, sessions, memory, documents, caches
- `logs\launcher.log` and `logs\server.log`

The install folder stays clean — verified byte-identical across runs (V7; re-verified for the Mission 2 build in M2-W5).

## Development

Run from source (repo root):

```powershell
python -m venv .venv
.venv\Scripts\pip install -r vendor\dobby\requirements.txt -r requirements-launcher.txt
.venv\Scripts\python -m launcher --console
```

## Verification

V-score 9/9 — all nine verification checks (V1–V9) passed against the built artifact; raw evidence in `docs/verification/`. Mission 2: W-score 5/5 — all five Mission 2 checks (M2-W1–M2-W5) passed against the rebuilt artifact; raw evidence in `docs/verification/M2-W*.txt`. Mission 3: W-score 1/1 — the Mission 3 check (M3-W6: frozen MCP schemas 47/47 non-empty + regression trio) passed against the rebuilt artifact at pin `01ce7cd`; raw evidence in `docs/verification/M3-W6.txt`.

## Source availability (AGPL)

This repository is AGPL-3.0-or-later. The complete corresponding source is this repository plus the pinned `vendor/dobby` submodule commit. The submodule repository (github.com/xicoocosta/dobby) is currently **private**, so the built zip is for personal use only — before distributing `DobbyOS-win64.zip` (or any binary built from this repo) to others, the dobby repository must be made public (or its source otherwise provided) to satisfy the AGPL §13 / corresponding-source obligations.

## Packaging caveats

- **Self-signed executable (at best).** The build signs `DobbyOS.exe` with a locally generated self-signed certificate (`CN=Dobby OS Desktop (self-signed)`, generated once into `%LOCALAPPDATA%\Dobby\signing\`, never committed) — if certificate generation fails on the build machine, the exe ships unsigned instead. Either way Windows SmartScreen still shows an "unrecognized app" warning on first run (More info → Run anyway): a self-signed signature provides file integrity and a stable publisher identity, not SmartScreen reputation — that requires a paid CA-issued certificate, planned for a later release. To verify integrity of a downloaded build, check the hashes in `dist\SHA256SUMS.txt` (standard `sha256sum -c` format, covers `DobbyOS.exe` and `DobbyOS-win64.zip`). Some antivirus engines may still false-positive on a PyInstaller-built exe; the build is onedir (not onefile), which already reduces AV heuristic flags — if your AV still flags it, add an exclusion for the install folder.
- **Firewall prompt on first launch.** The server binds `127.0.0.1:7001` (loopback only). Windows Firewall may still ask for permission on first launch — allowing it does not expose anything to the network or the internet; there is no inbound internet exposure.
- **The `DobbyOS/` folder must stay intact.** This is a onedir bundle: `DobbyOS.exe` needs the `_internal/` folder next to it (the dobby application tree ships inside it and is resolved via the launcher's base-dir probe). Move, copy, or zip the whole `DobbyOS/` folder — never the exe alone.
- **Optional features disabled or degraded:**
  - Built-in MCP servers are **enabled** (since Mission 2). The four server scripts ship under `_internal/dobby/mcp_servers/` and run with the exe itself as their interpreter (`ODYSSEUS_MCP_PYTHON` points at `DobbyOS.exe`, whose script role gives it python-like `exe script.py` semantics).
  - Runtime pip installs and the agent's Python tool don't work from a frozen exe (there is no pip inside the bundle) — a frozen-exe limitation.
  - `requirements-optional.txt` extras are not bundled: local speech-to-text (faster-whisper), DuckDuckGo search provider (ddgs), PDF form-filling (PyMuPDF), AI background removal (rembg), AI upscale (realesrgan), browser automation (playwright), and Office/EPUB extraction (markitdown). The app degrades gracefully where these are missing, but they cannot be pip-installed into the frozen bundle.
