$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$RuntimeDir = Join-Path $ProjectRoot "runtime"
$PackageDir = Join-Path $ProjectRoot "offline_packages"
$PythonArchive = Join-Path $RuntimeDir "cpython-3.14.7+20260814-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz"
$PythonUrl = "https://github.com/astral-sh/python-build-standalone/releases/download/20260814/cpython-3.14.7+20260814-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz"
$PythonSha256 = "cefba034445d2875408d1fd4d5700ae6731563aeb54dcb39fd8164ab5c457533"
New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null
New-Item -ItemType Directory -Force -Path $PackageDir | Out-Null
Write-Host "=== Validation Offline Bundle Preparation ===" -ForegroundColor Cyan
if (-not (Test-Path $PythonArchive)) {
    Write-Host "[DOWNLOAD] Python 3.14.7 Linux x86_64 runtime..."
    Invoke-WebRequest -Uri $PythonUrl -OutFile $PythonArchive
} else { Write-Host "[SKIP] Python archive already exists." }
Write-Host "[VERIFY] Python archive SHA256..."
$actualHash = (Get-FileHash -Algorithm SHA256 $PythonArchive).Hash.ToLowerInvariant()
if ($actualHash -ne $PythonSha256) { throw "Python runtime SHA256 mismatch. Expected $PythonSha256 but got $actualHash" }
Write-Host "[OK] Python runtime checksum verified."
Write-Host "[DOWNLOAD] Python wheels for Linux x86_64 / CPython 3.14..."
$requirements = Join-Path $ProjectRoot "Data_Parser\requirements.txt"
$forwarderReq = Join-Path $ProjectRoot "Data_Forwarder\requirements.txt"
$routerReq = Join-Path $ProjectRoot "Data_Router\requirements.txt"
$consoleReq = Join-Path $ProjectRoot "Web_Console\requirements.txt"
python -m pip download --dest $PackageDir --platform manylinux_2_17_x86_64 --python-version 3.14 --implementation cp --only-binary=:all: -r $requirements -r $forwarderReq -r $routerReq -r $consoleReq
if ($LASTEXITCODE -ne 0) { throw "Offline wheel download failed. No deployment bundle was produced." }
Write-Host "[OK] Offline package bundle prepared." -ForegroundColor Green
Write-Host "Runtime: $PythonArchive"
Write-Host "Packages: $PackageDir"
Write-Host "Copy the complete Validation directory to the offline Ubuntu machine."
