"""Frozen-exe entry wrapper (Phase 4 entry fix).

PyInstaller runs the Analysis entry script as a top-level script named
"__main__" with NO package context, so freezing launcher/__main__.py directly
makes its relative imports (e.g. ``from .logging_setup import ...``) raise
"attempted relative import with no known parent package" before logging even
starts. This wrapper is the entry script instead: it imports ``launcher`` as a
real package, so relative imports work, and because main() reads sys.argv
itself (argv=None default), the frozen --serve child spawned as
``[sys.executable, "--serve"]`` keeps working unchanged.
"""

import sys

from launcher.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
