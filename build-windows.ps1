# build-windows.ps1 — Phase 4 build driver for the Dobby OS desktop exe.
# Authored in Phase 3 (Packager). PowerShell 5.1-compatible: no && / || pipeline
# chains, no ternary. Native commands do not throw on failure in PS 5.1, so
# every native call is followed by an explicit $LASTEXITCODE check.

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$Py = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

function Write-Banner {
    param([string]$Text)
    Write-Host ""
    Write-Host "==================================================================="
    Write-Host $Text
    Write-Host "==================================================================="
}

function Assert-Native {
    param([string]$What)
    if ($LASTEXITCODE -ne 0) {
        Write-Host "FATAL: $What failed (exit code $LASTEXITCODE)"
        exit 1
    }
}

# ---------------------------------------------------------------------------
Write-Banner "[1/7] Verify .venv + Python version"
# ---------------------------------------------------------------------------
if (-not (Test-Path $Py)) {
    Write-Host ".venv not found - creating with 'py -3.12 -m venv .venv'"
    py -3.12 -m venv .venv
    Assert-Native "venv creation"
}
& $Py --version
Assert-Native "python --version"

# ---------------------------------------------------------------------------
Write-Banner "[2/7] Sync submodule + verify pinned gitlink"
# ---------------------------------------------------------------------------
git submodule update --init --checkout
Assert-Native "git submodule update"

$actual = (git -C vendor/dobby rev-parse HEAD).Trim()
Assert-Native "git rev-parse in vendor/dobby"

$lsTree = git ls-tree HEAD vendor/dobby
Assert-Native "git ls-tree HEAD vendor/dobby"
# ls-tree line format: "160000 commit <sha>\tvendor/dobby"
$pinned = ($lsTree -split "\s+")[2]

Write-Host "pinned  gitlink: $pinned"
Write-Host "checked out at : $actual"
if ($actual -ne $pinned) {
    Write-Host "FATAL: vendor/dobby HEAD does not match the pinned gitlink - aborting."
    exit 1
}
Write-Host "submodule OK: vendor/dobby is at the pinned commit"

# Working-tree cleanliness gate: a matching HEAD is not enough — local edits
# in vendor/dobby would ship unpinned source into the bundle.
$porcelain = git -C vendor/dobby status --porcelain
Assert-Native "git status --porcelain in vendor/dobby"
if ($porcelain) {
    Write-Host "vendor/dobby working tree status (porcelain):"
    $porcelain | ForEach-Object { Write-Host "  $_" }
    Write-Host "FATAL: vendor/dobby working tree is dirty - the pinned-source guarantee would be violated."
    exit 1
}
Write-Host "submodule OK: vendor/dobby working tree is clean"

# ---------------------------------------------------------------------------
Write-Banner "[3/7] Install dependencies into .venv (+ record versions)"
# ---------------------------------------------------------------------------
# pyinstaller pinned to 6.x: the spec's datas-landing analysis assumes the 6.x _internal/_MEIPASS onedir layout.
& $Py -m pip install -r vendor/dobby/requirements.txt -r requirements-launcher.txt "pyinstaller>=6,<7"
Assert-Native "pip install"

if (-not (Test-Path "build")) {
    New-Item -ItemType Directory -Path "build" | Out-Null
}
& $Py -m pip freeze | Out-File "build\pip-freeze.txt" -Encoding utf8
Assert-Native "pip freeze"
Write-Host "dependency versions recorded to build\pip-freeze.txt (for the run record)"

# ---------------------------------------------------------------------------
Write-Banner "[4/7] Frontend build step"
# ---------------------------------------------------------------------------
# NONE by design: Phase 0 verified vendor/dobby/static/ (254 files) is
# committed as-is with no build step - nothing to run, no npm required.
Write-Host "SKIP: static/ is committed prebuilt (254 files, Phase 0 verified); no npm step exists."

# ---------------------------------------------------------------------------
Write-Banner "[5/7] PyInstaller build (dobby-desktop.spec)"
# ---------------------------------------------------------------------------
& $Py -m PyInstaller dobby-desktop.spec --noconfirm
Assert-Native "pyinstaller"

# ---------------------------------------------------------------------------
Write-Banner "[6/7] Artifact summary"
# ---------------------------------------------------------------------------
$dist = Join-Path $PSScriptRoot "dist\DobbyOS"
if (-not (Test-Path (Join-Path $dist "DobbyOS.exe"))) {
    Write-Host "FATAL: expected artifact not found: $dist\DobbyOS.exe"
    exit 1
}
$files = Get-ChildItem -Path $dist -Recurse -File
$count = ($files | Measure-Object).Count
$bytes = ($files | Measure-Object -Property Length -Sum).Sum
$sizeMB = [math]::Round($bytes / 1MB, 1)
Write-Host "artifact   : $dist"
Write-Host "file count : $count (recursive)"
Write-Host "total size : $sizeMB MB"

# ---------------------------------------------------------------------------
Write-Banner "[7/7] Zip the onedir folder"
# ---------------------------------------------------------------------------
$zip = Join-Path $PSScriptRoot "dist\DobbyOS-win64.zip"
if (Test-Path $zip) {
    Remove-Item $zip -Force
}
# Zip the whole DobbyOS folder (onedir must stay intact - see README caveats).
Compress-Archive -Path $dist -DestinationPath $zip
$zipMB = [math]::Round((Get-Item $zip).Length / 1MB, 1)
Write-Host "zip        : $zip"
Write-Host "zip size   : $zipMB MB"

Write-Host ""
Write-Host "BUILD OK"
exit 0
