# -*- mode: python ; coding: utf-8 -*-
# dobby-desktop.spec — Phase 3 (Packager). PyInstaller onedir spec for Dobby OS.
#
# BINDING ARCHITECTURE (Gate 2): the dobby application ships as an ON-DISK
# SOURCE TREE inside the onedir bundle, NOT as frozen modules. The launcher's
# --serve child resolves the dobby base dir at runtime (launcher/paths.py:
# dobby_base_dir), chdirs there, sys.path-inserts it, then `import app` +
# uvicorn.run (launcher/server.py:155-185).
#
# PROBE-LANDING ANALYSIS (launcher/paths.py:65-77): frozen candidates are
#   1. <exe dir>/dobby              — MISS: PyInstaller 6.x onedir puts all
#                                     datas/Trees under <exe dir>/_internal
#   2. <exe dir>/vendor/dobby       — MISS: same reason
#   3. sys._MEIPASS/dobby           — HIT:  _MEIPASS == <exe dir>/_internal in
#                                     onedir, so every tuple below with dest
#                                     prefix 'dobby/...' lands exactly here
#   4. sys._MEIPASS/vendor/dobby    — not reached
# A candidate is valid only if it contains app.py AND static/ (paths.py:76) —
# both are shipped under the 'dobby/' prefix below, so candidate 3 validates.
#
# CONSEQUENCE: static analysis sees ONLY the launcher package's imports
# (webview, pystray, PIL, requests + function-level uvicorn — launcher/
# window.py:14, tray.py:15-16, server.py:24+181, ollama_check.py:22).
# Every dependency of dobby itself (vendor/dobby/requirements.txt, 33 specs)
# must be pulled in explicitly below. Each entry cites its evidence.

import os

from PyInstaller.utils.hooks import collect_all, collect_submodules

REPO = SPECPATH  # dir containing this spec = repo root
DOBBY = os.path.join(REPO, 'vendor', 'dobby')

# NOTE: no icon= is passed to EXE below — assets/dobby.ico does not exist in
# this repo (mission-mandated note). The tray glyph is generated at runtime
# with Pillow (launcher/tray.py:23-36), so no .ico is required to run.

# ---------------------------------------------------------------------------
# DATAS — the dobby on-disk source tree + the amended Phase-0 datas contract.
# Single files here; directory trees as Tree() objects further down (Tree
# supports excludes=, keeping __pycache__/*.pyc out of the bundle).
# ---------------------------------------------------------------------------
datas = [
    # DELTA (architecture): dobby's entry module. paths.py:76 requires app.py
    # to exist in the base dir; launcher/server.py:182 imports it by name.
    (os.path.join(DOBBY, 'app.py'), 'dobby'),

    # CONTRACT items 2-5: the 4 built-in MCP server scripts, referenced as
    # CWD-relative script paths at src/builtin_mcp.py:71-74 (the server role
    # chdirs to the base dir first — launcher/server.py:159). They ship as
    # data for a future re-enable even though ODYSSEUS_DISABLE_MCP=1 in v1
    # (launcher/server.py:44). mcp_servers/__init__.py is deliberately NOT
    # shipped: the scripts are launched by path, never imported as a package.
    (os.path.join(DOBBY, 'mcp_servers', 'image_gen_server.py'), 'dobby/mcp_servers'),
    (os.path.join(DOBBY, 'mcp_servers', 'memory_server.py'),    'dobby/mcp_servers'),
    (os.path.join(DOBBY, 'mcp_servers', 'rag_server.py'),       'dobby/mcp_servers'),
    (os.path.join(DOBBY, 'mcp_servers', 'email_server.py'),     'dobby/mcp_servers'),

    # CONTRACT item 6: hwfit model catalog, resolved relative to __file__ at
    # services/hwfit/models.py:258+268. Also contained in the services/ Tree
    # below — kept explicit for contract traceability (same source+dest, so
    # PyInstaller dedupes; no conflict).
    (os.path.join(DOBBY, 'services', 'hwfit', 'data', 'hf_models.json'),
     'dobby/services/hwfit/data'),

    # CONTRACT item 7 (conditional, gate-approved include): future-proofs the
    # setup flow; no runtime code reads it today (grep: zero references).
    (os.path.join(DOBBY, '.env.example'), 'dobby'),
]

# Directory trees. All prefixed 'dobby/' so they land at _MEIPASS/dobby (probe
# candidate 3). excludes keeps dev artifacts out of the shipped tree.
_TREE_EXCLUDES = ['__pycache__', '*.pyc', '*.pyo']

trees = [
    # CONTRACT item 1: the committed frontend — 254 files, no build step
    # (Phase 0). Mounted CWD-relative at vendor/dobby/app.py:415
    # (StaticFiles(directory="static")) and required by the paths.py:76 probe.
    Tree(os.path.join(DOBBY, 'static'), prefix='dobby/static', excludes=_TREE_EXCLUDES),

    # DELTA (architecture): dobby's Python packages. Evidence: the runtime
    # import tree (grep over app.py/src/routes/core/services/companion)
    # references EXACTLY these five top-level packages — src (775 froms),
    # core (304), routes (131+3), services (47), companion (2+1) — and app.py
    # imports all five (app.py:53-796). File counts: src 114 .py, routes 62,
    # core 10, services 39 (+hwfit data), companion 3.
    # NOT shipped (zero runtime imports/path refs, verified by grep):
    # tests/, docs/, tools/, scripts/, .sweep/, ds-reauthor/, assets/,
    # config/, skills/ (runtime skills live in <DATA_DIR>/skills —
    # services/memory/skills.py:66-67), migrations/ + alembic.ini + setup.py
    # (schema comes from Base.metadata.create_all — core/database.py:2494/
    # 3032; no runtime `import alembic` anywhere), node_modules, .git.
    Tree(os.path.join(DOBBY, 'src'),       prefix='dobby/src',       excludes=_TREE_EXCLUDES),
    Tree(os.path.join(DOBBY, 'routes'),    prefix='dobby/routes',    excludes=_TREE_EXCLUDES),
    Tree(os.path.join(DOBBY, 'core'),      prefix='dobby/core',      excludes=_TREE_EXCLUDES),
    Tree(os.path.join(DOBBY, 'services'),  prefix='dobby/services',  excludes=_TREE_EXCLUDES),
    Tree(os.path.join(DOBBY, 'companion'), prefix='dobby/companion', excludes=_TREE_EXCLUDES),

    # CONTRACT item 8 (conditional, gate-approved include): plugin zip
    # sources. routes/codex_routes.py:160 zips <base>/integrations/codex
    # wholesale for /api/codex/plugin.zip; routes/codex_routes.py:778 zips
    # <base>/integrations/claude/skills for /api/claude/plugin.zip.
    Tree(os.path.join(DOBBY, 'integrations', 'codex'),
         prefix='dobby/integrations/codex', excludes=_TREE_EXCLUDES),
    Tree(os.path.join(DOBBY, 'integrations', 'claude', 'skills'),
         prefix='dobby/integrations/claude/skills', excludes=_TREE_EXCLUDES),
]

# ---------------------------------------------------------------------------
# HIDDEN IMPORTS — dobby's code is data, so NOTHING it imports is visible to
# analysis. Everything below is driven by vendor/dobby/requirements.txt
# (33 specs) + a stdlib import sweep of the shipped source tree.
# ---------------------------------------------------------------------------

# (a) stdlib modules imported anywhere in the shipped dobby tree (sweep of
# app.py/src/routes/core/services/companion against sys.stdlib_module_names:
# 64 names). Excluded from the sweep result: __future__ (compile-time only),
# fcntl + pty (Unix-only, guarded imports at routes/shell_routes.py:24-25;
# they do not exist in Windows CPython). 'concurrent' listed as
# 'concurrent.futures' (the package alone imports nothing). email and urllib
# are handled by collect_submodules below (email.mime.* used at
# routes/email_helpers.py:25-26). Most of these are already pulled in by the
# launcher-side graph — listing them is a zero-cost determinism guarantee.
hidden_stdlib = [
    'abc', 'ast', 'asyncio', 'base64', 'collections', 'concurrent.futures',
    'contextlib', 'contextvars', 'copy', 'csv', 'ctypes', 'dataclasses',
    'datetime', 'difflib', 'enum', 'fnmatch', 'glob', 'hashlib', 'hmac',
    'html', 'imaplib', 'importlib', 'inspect', 'io', 'ipaddress', 'json',
    'logging', 'math', 'mimetypes', 'ntpath', 'os', 'pathlib', 'platform',
    'posixpath', 'random', 're', 'secrets', 'select', 'shlex', 'shutil',
    'signal', 'site', 'smtplib', 'socket', 'sqlite3', 'ssl', 'subprocess',
    'sys', 'tempfile', 'threading', 'time', 'traceback', 'types', 'typing',
    'unicodedata', 'uuid', 'wave', 'zipfile', 'zoneinfo',
]

# (b) third-party modules where a plain hiddenimport suffices (the package's
# own internal imports are static, so pulling the root pulls the graph, and
# any native extension lives inside the package and is found by the standard
# binary analysis / hooks). pip name -> import name mappings were verified by
# import probes in the project .venv (41/41 passed).
hidden_thirdparty = [
    'dotenv',                   # python-dotenv — vendor/dobby/app.py:30
    'bs4',                      # beautifulsoup4 — services/search/content.py
    'pypdf',                    # pypdf — PDF text extraction (requirements.txt:20)
    'pyotp',                    # pyotp — 2FA (requirements.txt:59)
    'croniter',                 # croniter — task scheduling (requirements.txt:61)
    'icalendar',                # icalendar — routes/calendar_routes.py
    'caldav',                   # caldav — src/caldav_sync.py (its deps lxml +
                                #   recurring_ical_events resolve statically;
                                #   vobject is absent in the dev venv too, so
                                #   parity is preserved by not forcing it)
    'nh3',                      # nh3 — Rust ext nh3/_nh3.pyd found via package
    'bcrypt',                   # bcrypt — app.py:65; Rust ext inside package
    'charset_normalizer',       # charset-normalizer — requirements.txt:22
    'youtube_transcript_api',   # youtube-transcript-api — services/youtube
    'defusedxml',               # NOT a direct requirement: transitive via
                                #   youtube-transcript-api (pip show
                                #   Required-by), lazily imported at
                                #   routes/contacts_routes.py:271 — invisible
                                #   to any analysis, so pinned here
    'httpx',                    # httpx — requirements.txt:12
    'pydantic',                 # pydantic v2 — requirements.txt:13
    'pydantic_core',            # native core of pydantic v2 (probe-verified);
                                #   the hooks-contrib pydantic hook also
                                #   covers this — explicit for determinism
    'pydantic_settings',        # pydantic-settings — requirements.txt:14
    'multipart',                # python-multipart 0.0.32 legacy import name
    'python_multipart',         # ...and its new import name; starlette 1.6.0
                                #   formparsers imports it lazily when a
                                #   Form/File route is first hit (upload
                                #   routes exist: routes/upload_routes.py)
    'matplotlib',               # matplotlib — requirements.txt:45; the
                                #   standard hook collects mpl-data once the
                                #   package is in the graph
    'matplotlib.pyplot',        # imported by src/project_export.py, invisible
    'matplotlib.backends.backend_agg',  # dobby forces the non-GUI Agg backend
                                #   itself at src/project_export.py:210
                                #   (matplotlib.use("Agg")) — the runtime
                                #   consideration lives in dobby, not here;
                                #   bundling the Agg backend makes it hold
    'numpy',                    # numpy — requirements.txt:23; standard hook
                                #   handles its DLLs
    'cryptography',             # cryptography — requirements.txt:56; the
                                #   standard/contrib hook collects the
                                #   _rust bindings + OpenSSL libs
    'cryptography.fernet',      # imported directly (2 sites, core/) —
                                #   invisible to analysis
    'h11',                      # uvicorn's only installed HTTP protocol impl
                                #   (probe: httptools/websockets/wsproto/
                                #   uvloop/watchfiles all ABSENT — plain
                                #   `uvicorn`, not uvicorn[standard])
    'clr',                      # pythonnet's import name — pywebview's
                                #   Windows (WinForms/WebView2) backend needs
                                #   it; probe-verified present
    'pystray._win32',           # backend chosen by sys.platform via a
                                #   function-level relative import
                                #   (pystray/__init__.py:34,48) — pinned so a
                                #   modulegraph change can never drop it
    'tokenizers',               # fastembed 0.8.0 dep (native ext; probe ok)
    'onnxruntime',              # fastembed dep — also collect_all'd below for
                                #   its capi DLLs; hiddenimport keeps the
                                #   module graph explicit
    'anyio._backends._asyncio', # anyio's backend loads via
                                #   import_module("anyio._backends._" + name)
                                #   (anyio/_core/_eventloop.py) — invisible to
                                #   static analysis; hooks-contrib's hook-anyio
                                #   also covers it, but this makes boot-critical
                                #   coverage explicit rather than resting on an
                                #   unpinned transitive hook package
]

# (c) collect_submodules — packages whose submodules are loaded by STRING or
# imported only by dobby code (invisible), so the static graph under-collects:
hidden_collected = []
for pkg, why in [
    ('uvicorn',   'loops/protocols/lifespan impls are string-loaded by '
                  'uvicorn.config (import_from_string) at runtime'),
    ('fastapi',   'dobby imports submodules analysis never sees: '
                  'fastapi.staticfiles/responses/middleware.cors (app.py:45-48)'),
    ('starlette', 'same: starlette.middleware.base/.gzip/responses/background '
                  '(app.py:49-50,69; routes/*)'),
    ('sqlalchemy','dobby imports sqlalchemy.orm/.engine/.types invisibly; the '
                  'sqlite dialect is selected from the "sqlite:///" URL string '
                  '(standard hook covers dialects — this is the deterministic '
                  'superset of it)'),
    ('markdown',  'extensions loaded BY NAME: ["extra","codehilite","toc",'
                  '"tables","sane_lists"] at src/visual_report.py:80'),
    ('pygments',  'codehilite dep (probe: present); lexers/formatters resolve '
                  'dynamically via name mappings'),
    ('qrcode',    'qrcode[pil] image factories (qrcode.image.*) are selected '
                  'at runtime'),
    ('dateutil',  'python-dateutil — dateutil.rrule imported by '
                  'routes/calendar_routes.py, invisible to analysis'),
    ('PIL',       'Pillow — launcher pulls only Image/ImageDraw/ImageFont '
                  '(tray.py:16); dobby has 13 `from PIL ...` sites analysis '
                  'never sees'),
    ('mcp',       'client transports imported lazily per connection type: '
                  'src/mcp_manager.py:182-327 (stdio/sse/streamable_http), '
                  'src/mcp_oauth.py:121-147; mcp is in requirements.txt:58 — '
                  'this collects the package already pulled by it, adding no '
                  'deps beyond requirements (mcp_servers scripts ship as data)'),
    ('email',     'stdlib: email.mime.* imported at routes/email_helpers.py:'
                  '25-26 and routes/email_pollers.py:29-30'),
    ('urllib',    'stdlib: urllib.request/parse/error used across the dobby '
                  'tree, invisible to analysis'),
]:
    hidden_collected += collect_submodules(pkg)

# (d) collect_all — packages that ship native DLLs or runtime data files that
# must travel with the package (verified by walking each package in .venv):
collect_all_datas, collect_all_binaries, collect_all_hidden = [], [], []
for pkg, why in [
    ('webview',    'pywebview 6.2.1: js/*.js + lib/ WebView2 DLLs '
                   '(Microsoft.Web.WebView2.Core.dll, WebBrowserInterop.'
                   'x64/x86.dll, runtimes/) — 15 non-py files; GUI backend '
                   'module is chosen dynamically at webview.start()'),
    ('pythonnet',  '97 DLLs (.NET bridge) required by the pywebview Windows '
                   'backend via `import clr`'),
    ('clr_loader', '2 loader DLLs used by pythonnet'),
    ('chromadb',   'chromadb-client 1.5.9 (import name `chromadb`, '
                   'probe-verified): ships log_config.yml + migrations/*.sql '
                   'data (25 non-py files) and resolves components from '
                   'settings strings'),
    ('fastembed',  'fastembed 0.8.0 — local ONNX embeddings '
                   '(requirements.txt:30); pure-py today (1 non-py file), '
                   'collect_all keeps its model-registry submodules complete'),
    ('onnxruntime','fastembed backend: native capi DLLs (2 .dll + 1 .pyd '
                   'inside the package) — deterministic regardless of the '
                   'hooks-contrib version Phase 4 installs'),
    ('pptx',       'python-pptx: templates/default.pptx + 8 more data files '
                   'required to construct a Presentation (src/project_export)'),
    ('docx',       'python-docx: 24 template data files (default.docx, '
                   'styles) required to construct a Document'),
    ('tzdata',     'zoneinfo on Windows has NO OS tz database — 600 zone '
                   'files; probe: ZoneInfo("Europe/Lisbon") resolves only '
                   'via tzdata; dobby imports zoneinfo'),
]:
    d, b, h = collect_all(pkg)
    collect_all_datas += d
    collect_all_binaries += b
    collect_all_hidden += h

hiddenimports = (hidden_stdlib + hidden_thirdparty + hidden_collected
                 + collect_all_hidden)

# EXCLUDED on purpose (requirements.txt entries with no runtime import):
#   pytest, pytest-asyncio (test runners), httpx2 (test-client only per
#   requirements.txt:64-66); alembic (CLI-only migration tooling — zero
#   `import alembic` in the runtime tree; schema is created by
#   Base.metadata.create_all, core/database.py:2494/3032).
# requirements-optional.txt (all excluded, all lazy/guarded in dobby, app
# degrades gracefully per that file's own header):
#   faster-whisper (services/tts + stt lazy), ddgs (search provider option),
#   PyMuPDF/fitz (AGPL; PDF form-filling only), rembg (bg removal, lazy at
#   use), realesrgan (commented out upstream; torch install-order trap),
#   playwright (browser automation; needs post-install browser download),
#   markitdown (lazy via src/markitdown_runtime.py; pdfminer import at
#   services/search/content.py:108 is try/except-guarded).
# tkinter excluded below: no GUI toolkit is used; matplotlib runs Agg
# (src/project_export.py:210) and Pillow's ImageTk path is never imported.

a = Analysis(
    [os.path.join(REPO, 'launcher', '__main__.py')],
    pathex=[REPO],
    binaries=collect_all_binaries,
    datas=datas + collect_all_datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter'],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='DobbyOS',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,                # mission requirement: reduces AV false positives
    console=False,            # tray/window app; the --serve child's stdio is
                              # redirected to server.log by Popen handles
                              # (launcher/server.py:76-86), not the console
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # NOTE: no icon= — assets/dobby.ico does not exist in this repo; the tray
    # glyph is drawn at runtime (launcher/tray.py). Revisit when an .ico lands.
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    *trees,                   # dobby source tree + static + integrations —
                              # all land under _internal/ = sys._MEIPASS, so
                              # paths.py probe candidate 3 (_MEIPASS/dobby)
                              # resolves the base dir
    strip=False,
    upx=False,
    name='DobbyOS',
)
