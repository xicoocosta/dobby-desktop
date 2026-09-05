# build-release.ps1 — Mission 4 release driver: Inno Setup per-user installer
# + AGPL corresponding-source zip + shareable bundle.
#
# INPUT, not build: dist\DobbyOS is the build-windows.ps1 verified onedir and
# is treated as a frozen release input — this script NEVER rebuilds it. Gate
# [1/7] enforces the INVARIANT that the release packages exactly what
# build-windows.ps1 produced and checksummed: it recomputes DobbyOS.exe's
# SHA256 and requires it to match the hash build-windows.ps1 recorded in
# dist\SHA256SUMS.txt at build time (step [9/9]). Any hand-edit to dist after
# the build breaks that match and the release refuses to package it; a
# legitimate rebuild refreshes both the exe and the checksum file together,
# so rebuilds pass without touching this script.
#
# AGPL strategy (FIXED): the dobby repo is private, so recipients get the
# complete corresponding source IN the distribution (AGPL section 6(a)) as
# SOURCE-DobbyOS-1.1.0.zip next to the installer. No repo URL is offered as a
# source channel.
#
# PowerShell 5.1-compatible: no && / || chains, no ternary. Native commands do
# not throw in PS 5.1, so every native call is followed by an explicit
# $LASTEXITCODE check. Only step [5/7] (signing) is best-effort/non-fatal —
# same policy as build-windows.ps1 step 6.

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$Version        = "1.1.0"
# Frozen input pin, recorded at the end of Mission 3:
$PinnedDobby    = "01ce7cda371e9ff3d447d2e646d7fe9bf0a5cfbf"

$DistDir     = Join-Path $PSScriptRoot "dist\DobbyOS"
$ExePath     = Join-Path $DistDir "DobbyOS.exe"
$DistSums    = Join-Path $PSScriptRoot "dist\SHA256SUMS.txt"
$BuildDir    = Join-Path $PSScriptRoot "build"
$ReleaseDir  = Join-Path $PSScriptRoot "dist\release"
$SourceZip   = Join-Path $ReleaseDir "SOURCE-DobbyOS-$Version.zip"
$SetupExe    = Join-Path $ReleaseDir "DobbyOS-Setup-$Version.exe"
$ShareZip    = Join-Path $PSScriptRoot "dist\DobbyOS-$Version-share.zip"
$NoticePath  = Join-Path $BuildDir "SOURCE-NOTICE.txt"

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

# PS 5.1's Compress-Archive writes BACKSLASH entry names (non-spec zip) —
# Linux/macOS unzip would extract files literally named "a\b\c". Since the
# source zip is a cross-platform AGPL deliverable, build zips with .NET and
# forward-slash entry names instead.
Add-Type -AssemblyName System.IO.Compression | Out-Null
Add-Type -AssemblyName System.IO.Compression.FileSystem | Out-Null
function New-PortableZip {
    param(
        [string]$Root,        # directory whose CONTENTS become the zip
        [string]$Destination,
        [string]$RootPrefix = ""   # optional top-level folder inside the zip
    )
    if (Test-Path $Destination) { Remove-Item $Destination -Force -Confirm:$false }
    $rootFull = (Get-Item $Root).FullName.TrimEnd('\')
    $zip = [System.IO.Compression.ZipFile]::Open(
        $Destination, [System.IO.Compression.ZipArchiveMode]::Create)
    try {
        $files = Get-ChildItem -Path $rootFull -Recurse -File | Sort-Object FullName
        foreach ($f in $files) {
            $rel = $f.FullName.Substring($rootFull.Length + 1).Replace('\', '/')
            if ($RootPrefix -ne "") { $rel = "$RootPrefix/$rel" }
            [void][System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
                $zip, $f.FullName, $rel,
                [System.IO.Compression.CompressionLevel]::Optimal)
        }
    } finally {
        $zip.Dispose()
    }
}

# ---------------------------------------------------------------------------
Write-Banner "[1/7] Preconditions: frozen dist + pinned, clean submodule"
# ---------------------------------------------------------------------------
if (-not (Test-Path $ExePath)) {
    Write-Host "FATAL: release input missing: $ExePath"
    Write-Host "       (Run build-windows.ps1 first - this script never rebuilds.)"
    exit 1
}
# Internal-consistency gate: the release packages exactly what
# build-windows.ps1 produced AND checksummed. build-windows.ps1 step [9/9]
# writes dist\SHA256SUMS.txt as the last act of a successful build, so the
# recorded exe hash and the exe on disk always change together; a mismatch
# (or a missing checksum file) means dist was modified outside the build and
# must not be packaged.
if (-not (Test-Path $DistSums)) {
    Write-Host "FATAL: $DistSums is missing - dist has no build-time checksums."
    Write-Host "       (Rebuild with build-windows.ps1; its step [9/9] writes them.)"
    exit 1
}
$recordedLine = Get-Content $DistSums | Where-Object { $_ -match '^([0-9a-fA-F]{64})\s+\*?DobbyOS\.exe\s*$' } | Select-Object -First 1
if ($null -eq $recordedLine) {
    Write-Host "FATAL: no DobbyOS.exe entry found in $DistSums - cannot verify dist."
    Write-Host "       (Rebuild with build-windows.ps1; its step [9/9] writes them.)"
    exit 1
}
$recordedSha = ($recordedLine -split "\s+")[0].ToLower()
$exeSha = (Get-FileHash -Algorithm SHA256 -Path $ExePath).Hash.ToLower()
Write-Host "recorded sha256 (dist\SHA256SUMS.txt): $recordedSha"
Write-Host "actual   sha256 (DobbyOS.exe)        : $exeSha"
if ($exeSha -ne $recordedSha) {
    Write-Host "FATAL: dist does not match its own build-time checksums - rebuild with build-windows.ps1"
    Write-Host "       (dist was modified after the build; refusing to package it.)"
    exit 1
}
Write-Host "dist OK: exe matches the hash build-windows.ps1 recorded at build time"

# Same strictness as build-windows.ps1 step 2, WITHOUT the -AllowAheadSubmodule
# escape hatch: a release is only ever cut from the committed pin.
$actual = (git -C vendor/dobby rev-parse HEAD).Trim()
Assert-Native "git rev-parse in vendor/dobby"
$lsTree = git ls-tree HEAD vendor/dobby
Assert-Native "git ls-tree HEAD vendor/dobby"
$pinned = ($lsTree -split "\s+")[2]
Write-Host "pinned  gitlink: $pinned"
Write-Host "checked out at : $actual"
if ($pinned -ne $PinnedDobby) {
    Write-Host "FATAL: committed gitlink is not the Mission-3 pin ($PinnedDobby) - aborting."
    exit 1
}
if ($actual -ne $pinned) {
    Write-Host "FATAL: vendor/dobby HEAD does not match the pinned gitlink - aborting."
    exit 1
}
$porcelain = git -C vendor/dobby status --porcelain
Assert-Native "git status --porcelain in vendor/dobby"
if ($porcelain) {
    $porcelain | ForEach-Object { Write-Host "  $_" }
    Write-Host "FATAL: vendor/dobby working tree is dirty - the source zip would not match the binaries."
    exit 1
}
Write-Host "submodule OK: at pin $PinnedDobby, working tree clean"

$desktopHead = (git rev-parse HEAD).Trim()
Assert-Native "git rev-parse HEAD"
Write-Host "dobby-desktop HEAD: $desktopHead"

# Fresh output area (release dir + share zip only - dist\DobbyOS is untouched).
if (Test-Path $ReleaseDir) { Remove-Item $ReleaseDir -Recurse -Force -Confirm:$false }
New-Item -ItemType Directory -Path $ReleaseDir | Out-Null
if (Test-Path $ShareZip) { Remove-Item $ShareZip -Force -Confirm:$false }
if (-not (Test-Path $BuildDir)) { New-Item -ItemType Directory -Path $BuildDir | Out-Null }

# ---------------------------------------------------------------------------
Write-Banner "[2/7] AGPL corresponding-source zip (git archive x2 + manifest)"
# ---------------------------------------------------------------------------
# Layout inside the zip:
#   SOURCE-MANIFEST.txt                (top level, first thing a recipient sees)
#   dobby-desktop/...                  (this repo at HEAD)
#   dobby-desktop/vendor/dobby/...     (the dobby submodule at the pinned commit)
# Both trees come from `git archive` of exact commits - never the working tree -
# so the zip provably corresponds to recorded hashes.
$staging = Join-Path $BuildDir "source-staging"
if (Test-Path $staging) { Remove-Item $staging -Recurse -Force -Confirm:$false }
New-Item -ItemType Directory -Path $staging | Out-Null

$tmpDesktopZip = Join-Path $BuildDir "src-desktop.zip"
$tmpDobbyZip   = Join-Path $BuildDir "src-dobby.zip"
git archive --format=zip --prefix=dobby-desktop/ -o $tmpDesktopZip HEAD
Assert-Native "git archive (dobby-desktop HEAD)"
git -C vendor/dobby archive --format=zip --prefix=dobby-desktop/vendor/dobby/ -o $tmpDobbyZip $PinnedDobby
Assert-Native "git archive (vendor/dobby pinned)"
Expand-Archive -Path $tmpDesktopZip -DestinationPath $staging -Force
Expand-Archive -Path $tmpDobbyZip   -DestinationPath $staging -Force
Remove-Item $tmpDesktopZip, $tmpDobbyZip -Force -Confirm:$false

$today = Get-Date -Format "yyyy-MM-dd"
$manifest = @(
    "SOURCE MANIFEST - Dobby OS Desktop $Version",
    "Generated: $today by build-release.ps1",
    "",
    "This archive IS the complete corresponding source of Dobby OS Desktop",
    "$Version under AGPL-3.0 section 6(a): the source accompanies the binary",
    "distribution (the installer it was shipped next to).",
    "",
    "Contents (exact commits, exported with git archive):",
    "  dobby-desktop/               packaging repo, commit $desktopHead",
    "                               (repo URL omitted - distributed by its author)",
    "  dobby-desktop/vendor/dobby/  Dobby application, commit $PinnedDobby",
    "                               (repo URL omitted - private repository; this",
    "                               archive, not the repo, is the source channel)",
    "",
    "License: GNU AGPL-3.0 - see dobby-desktop/LICENSE.",
    "Keep this zip together with the installer when re-sharing the app."
)
$manifest | Out-File -FilePath (Join-Path $staging "SOURCE-MANIFEST.txt") -Encoding ascii

New-PortableZip -Root $staging -Destination $SourceZip
$srcMB = [math]::Round((Get-Item $SourceZip).Length / 1MB, 1)
Write-Host "source zip : $SourceZip ($srcMB MB)"
Remove-Item $staging -Recurse -Force -Confirm:$false

# ---------------------------------------------------------------------------
Write-Banner "[3/7] Generate SOURCE-NOTICE.txt (installed into {app} by the iss)"
# ---------------------------------------------------------------------------
$notice = @(
    "Dobby OS Desktop $Version is free software under the GNU AGPL-3.0 (see LICENSE).",
    "The COMPLETE corresponding source code is in SOURCE-DobbyOS-$Version.zip,",
    "which was distributed alongside the installer that installed this program",
    "(AGPL section 6(a): source accompanies the distribution).",
    "If you pass this program on to someone else, pass the SOURCE zip along with it."
)
$notice | Out-File -FilePath $NoticePath -Encoding ascii
Write-Host "wrote $NoticePath :"
$notice | ForEach-Object { Write-Host "  $_" }

# ---------------------------------------------------------------------------
Write-Banner "[4/7] Compile installer (ISCC, installer\dobby-desktop.iss)"
# ---------------------------------------------------------------------------
# Locate ISCC: PATH first, then the per-user and machine default installs.
$iscc = $null
$isccCmd = Get-Command "iscc" -ErrorAction SilentlyContinue
if ($null -ne $isccCmd) { $iscc = $isccCmd.Source }
if ($null -eq $iscc) {
    $candidates = @(
        (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"),
        "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
    )
    foreach ($c in $candidates) {
        if ($null -eq $iscc -and (Test-Path $c)) { $iscc = $c }
    }
}
if ($null -eq $iscc) {
    Write-Host "FATAL: ISCC.exe not found (PATH, per-user, or Program Files (x86))."
    exit 1
}
Write-Host "ISCC: $iscc"
& $iscc (Join-Path $PSScriptRoot "installer\dobby-desktop.iss")
Assert-Native "ISCC compile"
if (-not (Test-Path $SetupExe)) {
    Write-Host "FATAL: ISCC exited 0 but $SetupExe was not produced."
    exit 1
}
$setupMB = [math]::Round((Get-Item $SetupExe).Length / 1MB, 1)
Write-Host "setup exe  : $SetupExe ($setupMB MB)"

# ---------------------------------------------------------------------------
Write-Banner "[5/7] Authenticode sign the installer (best-effort, self-signed)"
# ---------------------------------------------------------------------------
# Same policy as build-windows.ps1 step 6: NEVER fatal. Reuses the Mission-2
# identity at %LOCALAPPDATA%\Dobby\signing so the installer and the exe inside
# it carry the SAME publisher. Self-signed = integrity + stable identity only;
# SmartScreen still warns (INSTALL.txt tells recipients what to expect).
$signOk = $false
$pfxPath = Join-Path $env:LOCALAPPDATA "Dobby\signing\dobby-selfsigned.pfx"
$certSubj = "CN=Dobby OS Desktop (self-signed)"
$cert = $null
if (Test-Path $pfxPath) {
    try {
        $cert = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2($pfxPath, "")
        Write-Host "using PFX: $pfxPath"
    } catch {
        Write-Host "WARN: could not load PFX ($($_.Exception.Message)) - trying the store fallback."
    }
} else {
    Write-Host "WARN: no PFX at $pfxPath - trying the store fallback."
}
if ($null -eq $cert) {
    try {
        $cert = Get-ChildItem Cert:\CurrentUser\My -ErrorAction Stop |
            Where-Object { $_.Subject -eq $certSubj -and $_.HasPrivateKey } |
            Sort-Object NotAfter -Descending | Select-Object -First 1
        if ($null -ne $cert) {
            Write-Host "using existing store cert: Cert:\CurrentUser\My\$($cert.Thumbprint)"
        }
    } catch {
        Write-Host "WARN: certificate store lookup failed: $($_.Exception.Message)"
    }
}
if ($null -eq $cert) {
    Write-Host "WARN: no signing certificate available - installer ships UNSIGNED."
} else {
    $sig = $null
    try {
        $sig = Set-AuthenticodeSignature -FilePath $SetupExe -Certificate $cert `
            -HashAlgorithm SHA256 -TimestampServer "http://timestamp.digicert.com" -ErrorAction Stop
    } catch {
        Write-Host "WARN: timestamped signing failed ($($_.Exception.Message)) - retrying without timestamp."
    }
    if ($null -eq $sig -or $null -eq $sig.SignerCertificate) {
        try {
            $sig = Set-AuthenticodeSignature -FilePath $SetupExe -Certificate $cert `
                -HashAlgorithm SHA256 -ErrorAction Stop
        } catch {
            Write-Host "WARN: signing failed entirely: $($_.Exception.Message) - installer ships UNSIGNED."
        }
    }
    if ($null -ne $sig -and $null -ne $sig.SignerCertificate) {
        $signOk = $true
        Write-Host "signature applied: Status=$($sig.Status) StatusMessage=$($sig.StatusMessage)"
        Write-Host "NOTE: Status=UnknownError/NotTrusted is EXPECTED for a self-signed cert."
    }
}
if (-not $signOk) {
    Write-Host "SIGNING: skipped/failed - best-effort step, release continues."
}

# ---------------------------------------------------------------------------
Write-Banner "[6/7] Assemble dist\release + SHA256SUMS.txt"
# ---------------------------------------------------------------------------
Copy-Item (Join-Path $PSScriptRoot "installer\INSTALL.txt") (Join-Path $ReleaseDir "INSTALL.txt") -Force
# Hashes AFTER signing (signing rewrites the exe). sha256sum binary format,
# ASCII (a PS 5.1 utf8 BOM breaks `sha256sum -c`).
$setupSha = (Get-FileHash -Algorithm SHA256 -Path $SetupExe).Hash.ToLower()
$srcSha   = (Get-FileHash -Algorithm SHA256 -Path $SourceZip).Hash.ToLower()
$sums = @(
    "$setupSha *DobbyOS-Setup-$Version.exe",
    "$srcSha *SOURCE-DobbyOS-$Version.zip"
)
$sumsPath = Join-Path $ReleaseDir "SHA256SUMS.txt"
$sums | Out-File -FilePath $sumsPath -Encoding ascii
Write-Host "wrote $sumsPath :"
$sums | ForEach-Object { Write-Host "  $_" }
Write-Host "release folder contents:"
Get-ChildItem $ReleaseDir | ForEach-Object { Write-Host ("  {0,12:N0}  {1}" -f $_.Length, $_.Name) }

# ---------------------------------------------------------------------------
Write-Banner "[7/7] Shareable wrapper zip (dist\DobbyOS-$Version-share.zip)"
# ---------------------------------------------------------------------------
# RootPrefix gives the zip a versioned top-level folder, so it extracts to
# DobbyOS-1.1.0\ instead of a generic "release\".
New-PortableZip -Root $ReleaseDir -Destination $ShareZip -RootPrefix "DobbyOS-$Version"

Write-Host "artifact sizes:"
$report = @(
    @{ Name = "DobbyOS-Setup-$Version.exe";  Path = $SetupExe },
    @{ Name = "SOURCE-DobbyOS-$Version.zip"; Path = $SourceZip },
    @{ Name = "SHA256SUMS.txt";              Path = $sumsPath },
    @{ Name = "INSTALL.txt";                 Path = (Join-Path $ReleaseDir "INSTALL.txt") },
    @{ Name = "DobbyOS-$Version-share.zip";  Path = $ShareZip }
)
foreach ($r in $report) {
    $len = (Get-Item $r.Path).Length
    Write-Host ("  {0,-32} {1,14:N0} bytes ({2} MB)" -f $r.Name, $len, [math]::Round($len / 1MB, 1))
}

Write-Host ""
Write-Host "RELEASE OK"
exit 0
