# RUN_RECORD — dobby-desktop packaging mission

Deliverable and run record are separate artifacts; this file documents the process honestly, including failures.

## Mission

Public repo dobby-desktop packages Dobby OS as a PyInstaller onedir Windows exe (pywebview window + pystray tray, server on 127.0.0.1:7001, external Ollama via detection ladder, all runtime data under %LOCALAPPDATA%\Dobby).
dobby is consumed as a git submodule at vendor/dobby pinned to 3268d170848ae730e89523ae80c3c31b16ec2e35.
The dobby repo is read-only input (Blocker policy: dobby-side changes are a separate mission).

## Gate log

Gate 0 (Phase 0 survey): APPROVED 2026-09-04. Decisions: (1) gh CLI installed by agents; auth delegated from the user's existing Git Credential Manager credential (adjusted at Phase 1 to in-process GH_TOKEN after gh auth login rejected the token for missing read:org scope — same credential, scope+identity prechecked); (2) submodule pinned to 3268d170848ae730e89523ae80c3c31b16ec2e35 on non-default branch redesign/baseline — accepted; (3) v1 launcher sets ODYSSEUS_DISABLE_MCP=1 — the built-in MCP subsystem (4 servers spawned via sys.executable) is frozen-exe-incompatible; accepted v1 feature cut, proper fix is a separate dobby-side mission; (4) bundle integrations/codex + integrations/claude/skills as datas — amended contract: 6 required + 2 conditional = 8.

## Phase 0 — agent reports (verbatim, appended retroactively)

# Phase 0 reports (verbatim) — for retroactive append into RUN_RECORD.md at Phase 1
# Mission: dobby-desktop Windows exe packaging. Date: 2026-09-04.

## AGENT REPORT 1 — Surveyor

AGENT: Surveyor
TASK: Phase 0 read-only reconnaissance of dobby fork
STATUS: complete

EVIDENCE:

════ T1 — Working copy identity ════
Path: C:\Users\Admin\Documents\dobby
Branch: redesign/baseline
HEAD: 3268d170848ae730e89523ae80c3c31b16ec2e35
  ("review(fix): unchecked deletes, and an ARIA role that hid its own siblings")
git status --porcelain: 0 lines → CLEAN
Pushed: YES — `git branch -r --contains HEAD` → `origin/redesign/baseline`;
  `git log origin/redesign/baseline..HEAD --oneline | wc -l` → 0
Default branch: main (`git symbolic-ref refs/remotes/origin/HEAD` → refs/remotes/origin/main)
Remote: origin = https://github.com/xicoocosta/dobby.git (fetch+push)
FLAG: HEAD is reachable on GitHub but on a NON-DEFAULT branch (redesign/baseline, not main).
  A submodule pin to 3268d17 works today; it breaks if that branch is ever force-pushed/deleted.

════ T2 — Packaging-file inventory ════
| File | Status/path |
|---|---|
| Odysseus.spec | NOT in fork (Glob **/*.spec over whole tree: 0 matches) — upstream existence NOT verified (no remote fetch performed) |
| build-windows-portable.ps1 | NOT in fork (Glob **/build-windows*: 0 matches) — upstream unverified |
| launcher.py | NOT in fork (Glob **/launcher.py: 0 matches) — upstream unverified |
| launch-windows.ps1 | PRESENT — C:\Users\Admin\Documents\dobby\launch-windows.ps1 (venv + pip install + setup.py + `python -m uvicorn app:app`, default port 7000) |
| build-macos-app.sh | PRESENT — C:\Users\Admin\Documents\dobby\build-macos-app.sh |
Present: 2/5. Also present (not on the list): launch-dobby-local.ps1 (the port-7001 launcher).

════ T3 — Environment audit (verbatim) ════
python --version        → `Python 3.12.10`                              PASS
pip show pyinstaller    → `Name: pyinstaller / Version: 6.21.0` (Location: C:\Users\Admin\AppData\Local\Programs\Python\Python312\Lib\site-packages)  PASS
gh --version            → Git Bash: `bash: gh: command not found`; PowerShell: `CommandNotFoundException`  FAIL
gh auth status          → same — gh CLI NOT INSTALLED                    FAIL
ollama --version        → `Warning: could not connect to a running Ollama instance / Warning: client version is 0.32.14`  PASS (installed; daemon not running at survey time)
Get-PSDrive C           → Used 911088672768 (≈848.5 GiB), Free 112997830656 (≈105.2 GiB)  PASS
node --version / npm    → `v24.17.0` / `11.13.0`                         PASS
Env checks passed: 5/7 (both gh checks fail — repo creation/push in later phases needs gh installed+authed, or plain git with credentials).

════ T4 — Launch-path analysis ════
Entry: NO `if __name__ == "__main__"` in app.py (grep exit 1). Server is started
  externally via uvicorn CLI: `python -m uvicorn app:app --host 127.0.0.1 --port $Port`
  (launch-dobby-local.ps1:125–134; launch-windows.ps1:148). FastAPI object created at
  app.py:82 (`app = FastAPI(...)`); lifespan wired at app.py:931.
Port 7001 — every mechanism:
  1. uvicorn CLI `--port` (launch-dobby-local.ps1:2 default 7001; launch-windows.ps1:17 default 7000). No port constant in app code.
  2. Docker only: `${APP_BIND:-127.0.0.1}:${APP_PORT:-7000}:7000` (docker-compose.yml:5).
  3. Loopback self-calls: internal_api_base() = ODYSSEUS_INTERNAL_BASE override, else http://127.0.0.1:$APP_PORT, else 7000 (src/constants.py:100–103). Also companion/pairing.py:27 reads APP_PORT (default 7000).
  ⚠ LAUNCHER CONTRACT: running uvicorn on 7001 without also setting APP_PORT=7001 (or ODYSSEUS_INTERNAL_BASE) breaks agent-tool loopback calls.
Data/config dir: MECHANISM EXISTS — src/constants.py:10
  `DATA_DIR = os.getenv("ODYSSEUS_DATA_DIR", os.path.join(BASE_DIR, "data"))`
  Declared single source of truth (src/constants.py:13–15); core/constants.py is a re-export shim (core/constants.py:11). Everything persisted hangs off DATA_DIR: sessions/memory/settings/auth/app.db etc. (src/constants.py:16–54). DB: `DATABASE_URL` env, default sqlite:///{DATA_DIR}/app.db (core/database.py:33). Own-env-var subpaths still defaulting under DATA_DIR: MAIL_ATTACHMENTS_DIR, FASTEMBED_CACHE_DIR (src/constants.py:57–58).
  Caveats: (a) DATA_DIR is NOT created at boot — only setup.py:53 and /api/ready (src/readiness.py:38) create it; core/database.py:3032 runs init_db() at import, so boot fails if %LOCALAPPDATA%\Dobby doesn't exist. Launcher must pre-create it. (b) `.env` is loaded from CWD (app.py:36); no .env exists in the working copy today. (c) app.py:415 mounts StaticFiles(directory="static") — RELATIVE path, so CWD must be the bundle root.
Health endpoint: GET /api/health (app.py:885–887, returns {"status":"healthy",...}), auth-exempt (app.py:184). Also /api/ready (app.py:889–898, 503-capable, NOT auth-exempt) and /api/version (app.py:880, exempt). Live probe: curl http://127.0.0.1:7001/api/health → connection refused (curl exit 7) — server not running at survey time.
OmniRoute :20128: NOT REQUIRED. String `20128` appears in ZERO .py files (grep: no matches). Only two comments remain saying it was removed from scope: src/control/providers.py:22, :342. routes/diagnostics_routes.py: no omniroute/20128 matches (grep exit 1). The exe does not need it to boot or to serve.

════ T5 — Frontend build ════
COMMITTED STATIC FILES, NO BUILD STEP.
  package.json scripts: lint, lint:count, typecheck, typecheck:count only — no build (package.json:16–21).
  No vite.config.*/webpack.config.*/rollup.config.* anywhere.
  Served from static/: app.py:415 `app.mount("/static", _RevalidatingStatic(directory="static"))`; HTML served via abs_join(BASE_DIR, "static/index.html"|"shell.html"|"login.html"|"backgrounds.html") (app.py:811, 827, 872, 878).
  static/ = 254 files tracked (git ls-files static | wc -l) = 254 on disk (find static -type f | wc -l).

════ T6 — Datas checklist (Phase-3 contract) ════
1. static\  (entire dir, 254 files) — mounted app.py:415; HTML at app.py:811/827/872/878; STATIC_DIR src/constants.py:9.
2. mcp_servers\image_gen_server.py — spawned BY FILE PATH as a stdio subprocess: src/builtin_mcp.py:71, 119–124 (command=sys.executable, args=[script_path], PYTHONPATH=base_dir).
3. mcp_servers\memory_server.py — src/builtin_mcp.py:72 (same mechanism; reconnect path src/mcp_manager.py:511–524).
4. mcp_servers\rag_server.py — src/builtin_mcp.py:73.
5. mcp_servers\email_server.py — src/builtin_mcp.py:74.
6. services\hwfit\data\hf_models.json — read module-relative: services/hwfit/models.py:258, 268.
7. (conditional) .env.example — only if setup.py's first-run flow is reused (setup.py:172–173 copies it to .env).
DATAS COUNT: 6 required + 1 conditional = 7.
⚠ Items 2–5 are .py files needed AS ON-DISK SCRIPTS, and they sys.path-hack the repo root and import src/core modules (e.g. mcp_servers/email_server.py:31,35,1020; image_gen_server.py:17,19; memory_server.py:17,34–35) — under PyInstaller, sys.executable is the exe, not python, so this subsystem breaks as-is. Escape hatch: ODYSSEUS_DISABLE_MCP=1 skips all built-ins (src/builtin_mcp.py:87, 92–94).
Verified NOT needed at runtime: migrations\ + alembic.ini (schema via Base.metadata.create_all — core/database.py:2494, module-level init_db() core/database.py:3032; zero alembic invocations in any .ps1/.bat/.sh/Dockerfile); assets\ (referenced only by dev tools tools/retro16/* and .sweep); config\searxng (docker-compose.yml:107 volume only); skills\ repo root (runtime skills live in DATA_DIR/skills — services/memory/skills.py:67); integrations\, ds-reauthor\, tools\, docs\ (no runtime .py references found).
[AUDITOR CORRECTION — see Defect 1: integrations\ IS read at runtime by routes/codex_routes.py:160 and :778.]

════ T7 — Dependency audit ════
requirements.txt: 67 lines, 33 package specs: fastapi, uvicorn, python-multipart>=0.0.31, python-dotenv, httpx, pydantic>=2.0, pydantic-settings>=2.14.2, SQLAlchemy, alembic, pypdf>=6.13.3, beautifulsoup4, charset-normalizer, numpy, chromadb-client, fastembed, youtube-transcript-api, markdown, nh3, python-pptx, python-docx, matplotlib, icalendar, python-dateutil, caldav, cryptography>=48.0.1, bcrypt, mcp, pyotp, qrcode[pil], croniter, pytest, pytest-asyncio, httpx2. (Mostly UNPINNED by design — comment at requirements.txt:4–6.) Also present: requirements-optional.txt, requirements.lock, uv.lock.
PyInstaller friction, grounded:
  - uvicorn: today launched by string `app:app` via CLI (launch-dobby-local.ps1:127–134). Phase-2 launcher must call uvicorn programmatically with the imported app object; uvicorn's loop/protocol classes are string-loaded internally → hiddenimports for uvicorn.loops/protocols/lifespan.
  - fastembed (src/embeddings.py:110; routes/embedding_routes.py:118,157,193,220): pulls onnxruntime native DLLs + tokenizers; downloads models at first use into FASTEMBED_CACHE_DIR under DATA_DIR (src/constants.py:58) — cache lands correctly under %LOCALAPPDATA%\Dobby.
  - matplotlib (src/project_export.py:209–211): needs its mpl-data (contrib hook handles); force a non-GUI backend.
  - SQLAlchemy: dialect resolved from URL string "sqlite:///" (core/database.py:33) — covered by the standard hook.
  - mcp + built-in servers: subprocess spawn via sys.executable (src/builtin_mcp.py:97; src/mcp_manager.py:522) — broken in frozen app (see T6); npx-based browser server needs npx on PATH (src/builtin_mcp.py:78–84).
  - Runtime pip installs: routes/shell_routes.py:1271–1282 (`sys.executable -m pip install`) and dynamic importlib.import_module/metadata (routes/shell_routes.py:300–301, 973–981, 1195–1210) — cannot work inside a frozen exe; feature degrades.
  - src/agent_tools/subprocess_tools.py:135 runs `sys.executable -I -c <code>` — same frozen-exe problem for the agent python tool.
Python version: no requires-python anywhere (pyproject.toml is pytest/ruff config only; setup.py has no python_requires). Observed constraints: launch-dobby-local.ps1:114–115 pins uv to `--python 3.12`; launch-windows.ps1 accepts 3.11+ (:81, :109). Installed 3.12.10 matches.

FILES WRITTEN: none (read-only agent)

COUNTS: datas: 6 required + 1 conditional = 7; requirements lines: 67 (33 packages); dirty files: 0; unpushed commits: 0; packaging files present: 2/5; env checks passed: 5/7; static files: 254 tracked = 254 on disk; health endpoints: 2 (/api/health, /api/ready).

OPEN ITEMS:
- Data-dir mechanism found: YES (ODYSSEUS_DATA_DIR, src/constants.py:10) — no Blocker. But launcher MUST pre-create the dir (nothing creates it at boot; core/database.py:3032 connects at import) and set APP_PORT to the chosen port.
- HEAD pushed: YES, but on non-default branch redesign/baseline (default is main) — pin the submodule to the commit hash and record the branch.
- Health endpoint found: YES (/api/health, auth-exempt) — server was NOT running during the survey, so it was verified in code only, not live.
- gh CLI not installed (both shells) — blocks GitHub repo creation/push phases until installed+authed or replaced with plain git.
- Upstream odysseus-dev/odysseus was NOT fetched (read-only scope, no remote GET) — whether Odysseus.spec / build-windows-portable.ps1 / launcher.py exist upstream is unverified; note package.json:4 points at a different upstream URL (github.com/pewdiepie-archdaemon/odysseus.git).
- Built-in MCP subsystem (4 scripts spawned via sys.executable) is architecturally incompatible with a frozen exe as-is; ODYSSEUS_DISABLE_MCP=1 (src/builtin_mcp.py:87) is the documented off-switch until a proper fix (e.g. multiprocess entry-point or bundled scripts + PYTHONPATH into an embedded interpreter).
- app.py:415 mounts static with a RELATIVE path — the launcher must set CWD to the bundle root (or Phase 3 patches it to STATIC_DIR).
- Ollama installed (client 0.32.14) but daemon not running; port 7001 not listening at survey time.

## AGENT REPORT 2 — Auditor

AGENT: Auditor
TASK: Phase 0 audit of Surveyor report
STATUS: complete

EVIDENCE:
1. DATA_DIR mechanism — PASS. src/constants.py:10 reads exactly `DATA_DIR = os.getenv("ODYSSEUS_DATA_DIR", os.path.join(BASE_DIR, "data"))`. Lines 16–54 hang every persisted path off DATA_DIR (SESSIONS_FILE…MEMORY_VECTORS_DIR), lines 13–15 carry the "single source of truth / ONLY place ODYSSEUS_DATA_DIR is read" comment, lines 57–58 MAIL_ATTACHMENTS_DIR/FASTEMBED_CACHE_DIR default under DATA_DIR. Claimed = observed, line-exact. The Blocker-policy trigger does NOT fire.
2. Health endpoint — PASS. app.py:885–887: `@app.get("/api/health")` returning `{"status": "healthy", ...}`; app.py:184: `"/api/health",` inside AUTH_EXEMPT_EXACT (block 175–187). Bonus consistency: /api/version at :880 and /api/ready at :889–898 (503-capable, absent from the exempt set) both as claimed.
3. Static mount — PASS. app.py:415: `app.mount("/static", _RevalidatingStatic(directory="static"), name="static")` — subclass of StaticFiles, directory is the RELATIVE literal "static". CWD caveat is real.
4. builtin_mcp — PASS. _BUILTIN_SERVERS maps the 4 mcp_servers/*.py at src/builtin_mcp.py:71–74; `python = sys.executable` at :97, `command=python` at :105, spawn loop at :119–124; `MCP_DISABLED = os.environ.get("ODYSSEUS_DISABLE_MCP", ...)` at :87 with early-return at :92–94. Disk shows exactly those 4 server scripts + __init__.py in mcp_servers/.
5. OmniRoute — PASS (claim holds; census incomplete, see MINOR). Grep `20128|omniroute` (case-insensitive) over **/*.py: only src/control/providers.py:22 and :342 (comments, as cited) plus .sweep/phase1_routing.py:13 (docstring, uncited). The string 20128 appears in NO .py file — all other hits are docs/*.md. Zero functional refs: TRUE.
6. Datas hunt — ONE MISSED ITEM (see MAJOR). Verified sub-claims: services/hwfit/models.py:258 and :268 both build `os.path.join(os.path.dirname(__file__), "data", "hf_models.json")` (file exists on disk); migrations/alembic NOT needed at runtime — schema via `Base.metadata.create_all(bind=engine)` at core/database.py:2494 inside init_db(), `init_db()` at module scope core/database.py:3032; grep for alembic across *.py/*.ps1/*.sh/*.yml + Dockerfile: hits only inside migrations/ itself and docs/redesign/tools/inventory.py — no runtime invocation (requirements.txt:16–18 comment confirms alembic was added for reversible dev-time migrations, consistent). Style packs: static/ top-level contains design-phase0/ and retro/ — the redesign packs live INSIDE static/, covered by datas item 1; no theme/pack/skin directory reads exist in runtime .py (grep style_pack|theme/ over app.py,src,routes,core,services: 0 hits). Repo-root skills/ unused at runtime: only joins are services/memory/skills.py:67 and src/constants.py:51, both under DATA_DIR. setup.py:172–173 (.env/.env.example, file exists), app.py:36 `load_dotenv(encoding="utf-8-sig")` from CWD, setup.py:53 + src/readiness.py:38 as the only DATA_DIR makedirs — all line-exact. THE MISS: routes/codex_routes.py:160 (`Path(__file__)...parent.parent / "integrations" / "codex"`, GET /api/codex/plugin.zip) and :778 (`... / "integrations" / "claude" / "skills"`, GET /api/claude/plugin.zip) read the repo integrations/ tree at runtime; routers mounted at app.py:776–777. Surveyor's NOT-needed list says "integrations/" unconditionally. Mitigation: both handlers raise a graceful 404 if the dir is absent (:161–162, :779–780) — feature loss, not boot failure.
7. Git facts — PASS. `git rev-parse HEAD` → 3268d170848ae730e89523ae80c3c31b16ec2e35; branch redesign/baseline; porcelain 0 lines; `git branch -r --contains HEAD` → origin/redesign/baseline; origin/HEAD → refs/remotes/origin/main.
8. requirements.txt — PASS. Recounted: 67 total lines, 33 non-comment non-blank specs (last spec is `httpx2`, test-client only per its comment :64–66). "Mostly unpinned per comment" accurate (floors comment spans :3–9; surveyor's ":4–6" falls inside it).
9. Loopback — PASS. src/constants.py:100–103: ODYSSEUS_INTERNAL_BASE override else `http://127.0.0.1:{APP_PORT or '7000'}`. Corroborated: companion/pairing.py:27 `int(os.environ.get("APP_PORT", "7000"))`; docker-compose.yml:5 `"${APP_BIND:-127.0.0.1}:${APP_PORT:-7000}:7000"`; launch-dobby-local.ps1 default Port 7001 (:2) with `python -m uvicorn app:app` (:125–134); launch-windows.ps1 default 7000 (:17), uvicorn at :148 — the 7001-vs-APP_PORT warning is genuine.
Extras verified: T2 presence (Odysseus.spec/build-windows-portable.ps1/launcher.py absent; launch-windows.ps1, build-macos-app.sh, launch-dobby-local.ps1 present); static 254 tracked = 254 on disk; mcp_servers sys.path hacks (email_server.py:31 insert + :35 `from src.constants import ...`; image_gen_server.py:17; memory_server.py:17; also rag_server.py:16, uncited); runtime-pip friction real (routes/shell_routes.py:1271–1282 `pip install` via sys.executable; src/agent_tools/subprocess_tools.py:135 `sys.executable -I -c`); npx browser server builtin_mcp.py:78–84. No internal contradictions found.

FILES WRITTEN: none (read-only agent)

COUNTS: spot-checks passed 8/9, defects found 3
- DEFECT 1 (MAJOR — missed datas item): T6 declares `integrations/` "NOT needed", but routes/codex_routes.py:160 and :778 read integrations/codex and integrations/claude/skills at runtime via Path(__file__), and both routers are mounted (app.py:776–777). Excluding it from the bundle silently breaks GET /api/codex/plugin.zip and /api/claude/plugin.zip (graceful 404, no crash). Datas checklist needs an 8th conditional item — ship integrations/codex + integrations/claude/skills, or record the feature loss as an accepted cut.
- DEFECT 2 (MINOR — incomplete citation): "only comments src/control/providers.py:22,:342" — a third .py mention exists at .sweep/phase1_routing.py:13 (docstring). Zero-functional-refs conclusion unaffected.
- DEFECT 3 (MINOR — incomplete citation): the frozen-exe sys.path-hack warning cites email/image_gen/memory servers but omits mcp_servers/rag_server.py:16, which has the identical hack; the breakage applies to all 4 spawned scripts.

VERDICT: COUNTERSIGNED WITH DEFECTS (1 MAJOR: add integrations/codex + integrations/claude/skills as conditional datas item or an accepted feature cut; 2 MINOR citation gaps). Every load-bearing fact — DATA_DIR env mechanism, health/auth, static mount, MCP spawn + off-switch, git state, requirements counts, port/loopback — verified line-exact. No fabrication detected; no re-run required.

OPEN ITEMS: T3 environment probes (python/pyinstaller/gh/ollama/node versions, 105.2 GiB free) not re-run — low risk, environment not code. Live probe of /api/health skipped (server not running; surveyor said the same). Upstream-repo comparison for T2 not fetched (read-only scope both sides). Uncritical line cites not individually opened: email_server.py:1020, memory_server.py:34–35, src/mcp_manager.py:511–524, src/project_export.py:209–211, shell_routes importlib lines :300–301/:973–981/:1195–1210 — the pattern class each belongs to was confirmed at sibling lines.

## AMENDED DATAS CONTRACT (post-audit, binding for Phase 3)
1. static\ (254 files)                                      REQUIRED
2. mcp_servers\image_gen_server.py                          REQUIRED (only if MCP not disabled)
3. mcp_servers\memory_server.py                             REQUIRED (only if MCP not disabled)
4. mcp_servers\rag_server.py                                REQUIRED (only if MCP not disabled)
5. mcp_servers\email_server.py                              REQUIRED (only if MCP not disabled)
6. services\hwfit\data\hf_models.json                       REQUIRED
7. .env.example                                             CONDITIONAL (only if setup.py first-run flow reused)
8. integrations\codex + integrations\claude\skills          CONDITIONAL (else /api/codex/plugin.zip + /api/claude/plugin.zip 404) [added by Auditor Defect 1]
COUNT: 6 required + 2 conditional = 8.

## Phase 1 — agent reports

_(appended at Gate 1)_
