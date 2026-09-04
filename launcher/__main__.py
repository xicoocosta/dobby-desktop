"""Entry point: ``python -m launcher`` (dev) / the frozen exe (Phase 4).

Roles:
  (default)         full app: server subprocess + window + tray
  --serve           internal: run the SERVER role (uvicorn in-process)
  --smoke N         full normal startup, then after N seconds trigger the
                    exact tray-Quit code path programmatically (automated
                    verification)
  --smoke-restart   with --smoke: also exercise the tray Restart-server
                    handler mid-run (new PID + fresh health poll)
  --console         mirror launcher.log to stderr (diagnostics)
"""

import argparse
import sys


def main(argv=None) -> int:
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
