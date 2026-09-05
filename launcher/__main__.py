"""Entry point: ``python -m launcher`` (dev) / the frozen exe (Phase 4).

Roles:
  (default)         full app: server subprocess + window + tray
  <script.py> ...   SCRIPT role: python-like semantics — run the .py file as
                    __main__ via runpy with the remaining args as its argv.
                    Lets the frozen exe BE the interpreter dobby names in
                    ODYSSEUS_MCP_PYTHON for its built-in MCP server scripts.
  --serve           internal: run the SERVER role (uvicorn in-process)
  --smoke N         full normal startup, then after N seconds trigger the
                    exact tray-Quit code path programmatically (automated
                    verification)
  --smoke-restart   with --smoke: also exercise the tray Restart-server
                    handler mid-run (new PID + fresh health poll)
  --console         mirror launcher.log to stderr (diagnostics)
"""

import argparse
import os
import runpy
import sys


def main(argv=None) -> int:
    # SCRIPT role — decided BEFORE argparse so a script path is never parsed
    # as a launcher flag. If the first CLI arg is an existing .py file,
    # behave like `python script.py args...`: dobby spawns each built-in MCP
    # server as `<ODYSSEUS_MCP_PYTHON> <script_path>` and the frozen exe is
    # that interpreter. This branch must never import GUI modules
    # (webview/pystray) — those imports stay lazy in the default branch below.
    raw = list(sys.argv[1:] if argv is None else argv)
    if raw and raw[0].endswith(".py") and os.path.isfile(raw[0]):
        script = raw[0]
        sys.argv = [script] + raw[1:]
        # Frozen exes ignore the PYTHONPATH env var; dobby passes its base
        # dir through it, so mirror its entries into sys.path (prepended,
        # original order preserved). Each dobby script self-bootstraps the
        # rest of its import environment.
        for entry in reversed(os.environ.get("PYTHONPATH", "").split(os.pathsep)):
            if entry:
                sys.path.insert(0, entry)
        runpy.run_path(script, run_name="__main__")
        # Script exceptions propagate -> nonzero exit, traceback on stderr
        # (the parent pipes stderr).
        return 0

    parser = argparse.ArgumentParser(
        prog="launcher", description="Dobby OS desktop launcher")
    parser.add_argument("--console", action="store_true",
                        help="also log to stderr (diagnostics)")
    parser.add_argument("--serve", action="store_true",
                        help="internal: run the server role")
    parser.add_argument("--smoke", type=float, metavar="N", default=None,
                        help="smoke test: full startup, auto-quit after N seconds")
    parser.add_argument("--smoke-restart", action="store_true",
                        help="with --smoke: also exercise the restart handler")
    args = parser.parse_args(argv)

    if args.serve:
        from .server import serve
        serve()
        return 0

    from .logging_setup import setup_logging
    setup_logging(console=args.console)

    from .app import App
    app = App(smoke=args.smoke, smoke_restart=args.smoke_restart)
    return app.run()


if __name__ == "__main__":
    sys.exit(main())
