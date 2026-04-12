#Requires -Version 5.1
<#
.SYNOPSIS
    Build the Omniclaw Windows installer end-to-end.

.DESCRIPTION
    1. Builds the React frontend (npm)
    2. Copies the build output into mcp-server/static/
    3. Bundles the Python backend with PyInstaller
    4. (Optional) Downloads the Ollama installer for bundling
    5. Compiles the Inno Setup installer

.PARAMETER SkipFrontend
    Skip the npm build step (use existing static/ folder).

.PARAMETER SkipOllamaDownload
    Skip downloading the Ollama installer to bundle in the setup.

.PARAMETER InnoSetupPath
    Path to ISCC.exe.  Defaults to the standard Inno Setup 6 location.
#>
param(
    [switch]$SkipFrontend,
    [switch]$SkipOllamaDownload,
    [string]$InnoSetupPath = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
)

$ErrorActionPreference = "Stop"

$Root       = Split-Path -Parent $MyInvocation.MyCommand.Definition
$Frontend   = Join-Path $Root "frontend"
$Server     = Join-Path $Root "mcp-server"
$StaticDest = Join-Path $Server "static"
$Installer  = Join-Path $Root "installer"

function Write-Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }

# ── 1. Build frontend ────────────────────────────────────────────────────────

if (-not $SkipFrontend) {
    Write-Step "Building React frontend"
    Push-Location $Frontend
    try {
        npm install
        if ($LASTEXITCODE -ne 0) { throw "npm install failed" }

        npm run build
        if ($LASTEXITCODE -ne 0) { throw "npm run build failed" }
    } finally {
        Pop-Location
    }

    $FrontendDist = Join-Path $Frontend "dist"
    if (-not (Test-Path $FrontendDist)) {
        throw "Frontend build output not found at $FrontendDist"
    }

    Write-Step "Copying frontend build to mcp-server/static/"
    if (Test-Path $StaticDest) { Remove-Item $StaticDest -Recurse -Force }
    Copy-Item $FrontendDist $StaticDest -Recurse
} else {
    Write-Host "Skipping frontend build (--SkipFrontend)" -ForegroundColor Yellow
    if (-not (Test-Path $StaticDest)) {
        throw "static/ folder not found. Run without -SkipFrontend first."
    }
}

# ── 2. PyInstaller bundle ────────────────────────────────────────────────────

Write-Step "Bundling with PyInstaller"
Push-Location $Server
try {
    pip install pyinstaller --quiet
    if ($LASTEXITCODE -ne 0) { throw "pip install pyinstaller failed" }

    pyinstaller omniclaw.spec --noconfirm --clean
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed" }
} finally {
    Pop-Location
}

$DistDir = Join-Path $Server "dist\omniclaw"
if (-not (Test-Path $DistDir)) {
    throw "PyInstaller output not found at $DistDir"
}
Write-Host "PyInstaller bundle ready at $DistDir" -ForegroundColor Green

# ── 3. Download Ollama installer (optional) ──────────────────────────────────

$OllamaSetup = Join-Path $Installer "OllamaSetup.exe"
if (-not $SkipOllamaDownload) {
    Write-Step "Downloading Ollama installer"
    $OllamaUrl = "https://ollama.com/download/OllamaSetup.exe"
    try {
        Invoke-WebRequest -Uri $OllamaUrl -OutFile $OllamaSetup -UseBasicParsing
        Write-Host "Ollama installer saved to $OllamaSetup" -ForegroundColor Green
    } catch {
        Write-Warning "Could not download Ollama installer: $_"
        Write-Warning "The installer will prompt users to download it manually."
    }
} else {
    Write-Host "Skipping Ollama download (--SkipOllamaDownload)" -ForegroundColor Yellow
}

# ── 4. Compile Inno Setup installer ──────────────────────────────────────────

Write-Step "Compiling Inno Setup installer"

if (-not (Test-Path $InnoSetupPath)) {
    Write-Warning "Inno Setup compiler not found at: $InnoSetupPath"
    Write-Warning "Install Inno Setup 6 from https://jrsoftware.org/issetup.php"
    Write-Warning "Or pass -InnoSetupPath to this script."
    Write-Host "`nPyInstaller bundle is ready at: $DistDir" -ForegroundColor Yellow
    Write-Host "You can compile the installer manually later." -ForegroundColor Yellow
    exit 0
}

$IssFile = Join-Path $Installer "omniclaw.iss"
& $InnoSetupPath $IssFile
if ($LASTEXITCODE -ne 0) { throw "Inno Setup compilation failed" }

$SetupExe = Join-Path $Installer "Output\OmniclawSetup.exe"
Write-Host "`n============================================" -ForegroundColor Green
Write-Host "  Build complete!" -ForegroundColor Green
Write-Host "  Installer: $SetupExe" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
