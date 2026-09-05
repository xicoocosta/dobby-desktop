# build-windows.ps1 — build driver for the Dobby OS desktop exe.
# Authored in Phase 3 (Packager); Mission 2 added the version resource,
# best-effort Authenticode self-signing, and SHA256 checksums.
# PowerShell 5.1-compatible: no && / || pipeline chains, no ternary. Native
# commands do not throw on failure in PS 5.1, so every native call is followed
# by an explicit $LASTEXITCODE check. The script exits non-zero only on
# REQUIRED step failures — signing (step 6) is best-effort and never fatal.
#
# -AllowAheadSubmodule: build while vendor/dobby is intentionally checked out
# AHEAD of the committed gitlink (an in-flight pin advance, e.g. mid-mission
# before the gitlink commit lands). The submodule worktree must still be clean
# and HEAD must be a DESCENDANT of the pinned commit. Never use for a release
# build — commit the gitlink instead.

param(
    [switch]$AllowAheadSubmodule
)

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
Write-Banner "[1/9] Verify .venv + Python version"
# ---------------------------------------------------------------------------
if (-not (Test-Path $Py)) {
    Write-Host ".venv not found - creating with 'py -3.12 -m venv .venv'"
    py -3.12 -m venv .venv
    Assert-Native "venv creation"
}
& $Py --version
Assert-Native "python --version"

# ---------------------------------------------------------------------------
Write-Banner "[2/9] Sync submodule + verify pinned gitlink"
# ---------------------------------------------------------------------------
if ($AllowAheadSubmodule -and (Test-Path "vendor\dobby\app.py")) {
    Write-Host "WARN: -AllowAheadSubmodule - skipping 'git submodule update' so an"
    Write-Host "      intentionally advanced vendor/dobby worktree is not reverted"
    Write-Host "      to the committed gitlink."
} else {
    git submodule update --init --checkout
    Assert-Native "git submodule update"
}

$actual = (git -C vendor/dobby rev-parse HEAD).Trim()
Assert-Native "git rev-parse in vendor/dobby"

$lsTree = git ls-tree HEAD vendor/dobby
Assert-Native "git ls-tree HEAD vendor/dobby"
# ls-tree line format: "160000 commit <sha>\tvendor/dobby"
$pinned = ($lsTree -split "\s+")[2]

Write-Host "pinned  gitlink: $pinned"
Write-Host "checked out at : $actual"
if ($actual -ne $pinned) {
    if ($AllowAheadSubmodule) {
        git -C vendor/dobby merge-base --is-ancestor $pinned $actual
        if ($LASTEXITCODE -eq 0) {
            Write-Host "WARN: vendor/dobby is AHEAD of the pinned gitlink (allowed by -AllowAheadSubmodule):"
            Write-Host "      pinned $pinned"
            Write-Host "      HEAD   $actual (a descendant of the pin)"
            Write-Host "      IN-FLIGHT build - commit the gitlink update before any release."
        } else {
            Write-Host "FATAL: vendor/dobby HEAD is not a descendant of the pinned gitlink -"
            Write-Host "       refusing even with -AllowAheadSubmodule."
            exit 1
        }
    } else {
        Write-Host "FATAL: vendor/dobby HEAD does not match the pinned gitlink - aborting."
        Write-Host "       (For an in-flight pin advance, re-run with -AllowAheadSubmodule.)"
        exit 1
    }
} else {
    Write-Host "submodule OK: vendor/dobby is at the pinned commit"
}

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
Write-Banner "[3/9] Install dependencies into .venv (+ record versions)"
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
Write-Banner "[4/9] Frontend build step"
# ---------------------------------------------------------------------------
# NONE by design: Phase 0 verified vendor/dobby/static/ (254 files) is
# committed as-is with no build step - nothing to run, no npm required.
Write-Host "SKIP: static/ is committed prebuilt (254 files, Phase 0 verified); no npm step exists."

# ---------------------------------------------------------------------------
Write-Banner "[5/9] PyInstaller build (dobby-desktop.spec)"
# ---------------------------------------------------------------------------
& $Py -m PyInstaller dobby-desktop.spec --noconfirm
Assert-Native "pyinstaller"

$dist = Join-Path $PSScriptRoot "dist\DobbyOS"
$exePath = Join-Path $dist "DobbyOS.exe"

# ---------------------------------------------------------------------------
Write-Banner "[6/9] Authenticode sign DobbyOS.exe (best-effort, self-signed)"
# ---------------------------------------------------------------------------
# BEST-EFFORT and NEVER FATAL: without a paid certificate the most we can ship
# is a self-signed signature — integrity + a stable publisher identity, NOT
# SmartScreen reputation (SmartScreen warns either way). Key material lives
# OUTSIDE the repo in %LOCALAPPDATA%\Dobby\signing\ and is generated once,
# then reused so the identity stays stable across builds. Every fallback taken
# is printed; if everything fails the exe simply ships unsigned.
$signOk = $false
if (-not (Test-Path $exePath)) {
    Write-Host "WARN: $exePath not found - skipping signing (step 7 fails the build)."
} else {
    $signDir  = Join-Path $env:LOCALAPPDATA "Dobby\signing"
    $pfxPath  = Join-Path $signDir "dobby-selfsigned.pfx"
    $openssl  = "C:\Program Files\Git\usr\bin\openssl.exe"
    $certSubj = "CN=Dobby OS Desktop (self-signed)"

    if (-not (Test-Path $pfxPath)) {
        Write-Host "no PFX at $pfxPath - one-time self-signed cert generation"
        if (Test-Path $openssl) {
            try {
                if (-not (Test-Path $signDir)) {
                    New-Item -ItemType Directory -Path $signDir -Force | Out-Null
                }
                $keyPem = Join-Path $signDir "dobby-selfsigned.key"
                $crtPem = Join-Path $signDir "dobby-selfsigned.crt"
                # 3-year self-signed cert; EKU codeSigning is REQUIRED for
                # Set-AuthenticodeSignature to accept the cert.
                $reqArgs = @(
                    "req", "-x509", "-newkey", "rsa:3072", "-sha256",
                    "-days", "1095", "-nodes",
                    "-subj", "/CN=Dobby OS Desktop (self-signed)",
                    "-addext", "extendedKeyUsage=codeSigning",
                    "-keyout", $keyPem, "-out", $crtPem
                )
                & $openssl @reqArgs
                if ($LASTEXITCODE -ne 0) {
                    Write-Host "WARN: openssl req failed (exit $LASTEXITCODE) - no cert generated."
                } else {
                    # Passwordless PFX (-passout pass:). 3DES/SHA1 PBE + SHA1 MAC:
                    # maximum Windows CryptoAPI compatibility, still in OpenSSL 3.x
                    # default provider (the modern AES/PBES2 default is not readable
                    # by every Windows crypto stack).
                    $p12Args = @(
                        "pkcs12", "-export", "-inkey", $keyPem, "-in", $crtPem,
                        "-out", $pfxPath, "-passout", "pass:",
                        "-keypbe", "PBE-SHA1-3DES", "-certpbe", "PBE-SHA1-3DES",
                        "-macalg", "sha1"
                    )
                    & $openssl @p12Args
                    if ($LASTEXITCODE -ne 0) {
                        Write-Host "WARN: openssl pkcs12 -export failed (exit $LASTEXITCODE)."
                        if (Test-Path $pfxPath) { Remove-Item $pfxPath -Force -Confirm:$false }
                    } else {
                        Write-Host "generated: $pfxPath ($certSubj, 1095 days, EKU=codeSigning, passwordless)"
                    }
                }
            } catch {
                Write-Host "WARN: openssl generation path threw: $($_.Exception.Message)"
            }
        } else {
            Write-Host "WARN: openssl not found at $openssl - will try the certificate-store fallback."
        }
    } else {
        Write-Host "using existing PFX: $pfxPath"
    }

    # Load the signing cert: PFX first, then the CurrentUser\My store fallback
    # (created here if needed via New-SelfSignedCertificate — no PFX export on
    # that path because Export-PfxCertificate cannot write a passwordless PFX).
    $cert = $null
    if (Test-Path $pfxPath) {
        try {
            $cert = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2($pfxPath, "")
        } catch {
            Write-Host "WARN: could not load PFX ($($_.Exception.Message)) - trying the store fallback."
        }
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
        try {
            $cert = New-SelfSignedCertificate -Type CodeSigningCert -Subject $certSubj `
                -CertStoreLocation Cert:\CurrentUser\My -KeyAlgorithm RSA -KeyLength 3072 `
                -HashAlgorithm SHA256 -NotAfter (Get-Date).AddYears(3) -ErrorAction Stop
            Write-Host "generated store cert (fallback): Cert:\CurrentUser\My\$($cert.Thumbprint)"
        } catch {
            Write-Host "WARN: New-SelfSignedCertificate fallback failed: $($_.Exception.Message)"
        }
    }

    if ($null -eq $cert) {
        Write-Host "WARN: no signing certificate available via any path - DobbyOS.exe ships UNSIGNED."
    } else {
        Write-Host "signing cert: Subject=$($cert.Subject) Thumbprint=$($cert.Thumbprint) NotAfter=$($cert.NotAfter)"
        $sig = $null
        try {
            $sig = Set-AuthenticodeSignature -FilePath $exePath -Certificate $cert `
                -HashAlgorithm SHA256 -TimestampServer "http://timestamp.digicert.com" -ErrorAction Stop
        } catch {
            Write-Host "WARN: timestamped signing failed ($($_.Exception.Message)) - retrying without timestamp."
        }
        if ($null -eq $sig -or $null -eq $sig.SignerCertificate) {
            try {
                $sig = Set-AuthenticodeSignature -FilePath $exePath -Certificate $cert `
                    -HashAlgorithm SHA256 -ErrorAction Stop
            } catch {
                Write-Host "WARN: signing failed entirely: $($_.Exception.Message) - DobbyOS.exe ships UNSIGNED."
            }
        }
        if ($null -ne $sig -and $null -ne $sig.SignerCertificate) {
            $signOk = $true
            Write-Host "signature applied: Status=$($sig.Status) StatusMessage=$($sig.StatusMessage)"
            Write-Host "NOTE: Status=UnknownError/NotTrusted is EXPECTED for a self-signed cert (chain"
            Write-Host "      ends in an untrusted root). The signature still provides integrity + a"
            Write-Host "      stable publisher identity; it does NOT buy SmartScreen reputation."
        }
    }
}
if (-not $signOk) {
    Write-Host "SIGNING: skipped/failed - best-effort step, build continues, exe is unsigned."
}

# ---------------------------------------------------------------------------
Write-Banner "[7/9] Artifact summary"
# ---------------------------------------------------------------------------
if (-not (Test-Path $exePath)) {
    Write-Host "FATAL: expected artifact not found: $exePath"
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
Write-Banner "[8/9] Zip the onedir folder"
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

# ---------------------------------------------------------------------------
Write-Banner "[9/9] SHA256 checksums (dist\SHA256SUMS.txt)"
# ---------------------------------------------------------------------------
# REQUIRED step: with (at best) a self-signed signature, these hashes are the
# user-verifiable integrity story for the shipped artifacts.
$sumsPath = Join-Path $PSScriptRoot "dist\SHA256SUMS.txt"
$exeHash = (Get-FileHash -Algorithm SHA256 -Path $exePath).Hash.ToLower()
$zipHash = (Get-FileHash -Algorithm SHA256 -Path $zip).Hash.ToLower()
# Standard sha256sum binary-mode format: "<hash> *<filename>". ASCII encoding:
# PS 5.1 utf8 writes a BOM, which `sha256sum -c` rejects.
$sums = @(
    "$exeHash *DobbyOS.exe",
    "$zipHash *DobbyOS-win64.zip"
)
$sums | Out-File -FilePath $sumsPath -Encoding ascii
Write-Host "wrote $sumsPath :"
$sums | ForEach-Object { Write-Host "  $_" }

Write-Host ""
Write-Host "BUILD OK"
exit 0
