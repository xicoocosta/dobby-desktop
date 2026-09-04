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
