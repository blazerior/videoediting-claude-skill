# Installs the videoediting skill into the user's Claude Code skills folder.
# Usage: powershell -ExecutionPolicy Bypass -File scripts/install.ps1
#
# Kept strictly ASCII on purpose: Windows PowerShell 5.1 reads UTF-8 files
# without a BOM as ANSI, and any non-ASCII character breaks the parser.

$ErrorActionPreference = "Stop"

$repo = Split-Path -Parent $PSScriptRoot
$src = Join-Path $repo "skill\videoediting"
$dst = Join-Path $env:USERPROFILE ".claude\skills\videoediting"

if (-not (Test-Path $src)) {
    throw "skill/videoediting not found next to this script. Run it from inside the cloned repo."
}

Write-Host ""
Write-Host "Installing the videoediting skill" -ForegroundColor Cyan
Write-Host ""

if (Test-Path $dst) {
    Write-Host "  A skill already exists at $dst" -ForegroundColor Yellow
    $answer = Read-Host "  Overwrite? (y/N)"
    if ($answer -ne "y") {
        Write-Host "  Cancelled."
        exit 0
    }
    Remove-Item $dst -Recurse -Force
}

New-Item -ItemType Directory -Force (Split-Path $dst) | Out-Null
Copy-Item $src $dst -Recurse
Get-ChildItem $dst -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

Write-Host "  Installed to $dst" -ForegroundColor Green
Write-Host ""
Write-Host "Dependency check" -ForegroundColor Cyan
Write-Host ""

$missing = @()

foreach ($t in 'ffmpeg', 'ffprobe', 'python') {
    $c = Get-Command $t -ErrorAction SilentlyContinue
    if ($c) {
        Write-Host "  [ok]      $t" -ForegroundColor Green
    } else {
        Write-Host "  [MISSING] $t" -ForegroundColor Red
        $missing += $t
    }
}

$chromePaths = @(
    "C:\Program Files\Google\Chrome\Application\chrome.exe",
    "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
)
if ($chromePaths | Where-Object { Test-Path $_ }) {
    Write-Host "  [ok]      chrome" -ForegroundColor Green
} else {
    Write-Host "  [MISSING] chrome" -ForegroundColor Red
    $missing += "chrome"
}

$fwOk = $false
if (Get-Command python -ErrorAction SilentlyContinue) {
    & python -c "import faster_whisper" 2>$null
    if ($LASTEXITCODE -eq 0) { $fwOk = $true }
}
if ($fwOk) {
    Write-Host "  [ok]      faster-whisper" -ForegroundColor Green
} else {
    Write-Host "  [MISSING] faster-whisper   (pip install faster-whisper)" -ForegroundColor Red
    $missing += "faster-whisper"
}

if (Get-Command ffmpeg -ErrorAction SilentlyContinue) {
    $filters = & ffmpeg -hide_banner -filters 2>$null | Out-String
    foreach ($f in 'subtitles', 'lut3d', 'vidstabtransform', 'loudnorm') {
        if ($filters -match "\s$f\s") {
            Write-Host "  [ok]      filter: $f" -ForegroundColor Green
        } else {
            Write-Host "  [MISSING] filter: $f  (you need a full ffmpeg build)" -ForegroundColor Red
        }
    }
}

$free = [math]::Round((Get-PSDrive -Name $env:USERPROFILE.Substring(0, 1)).Free / 1GB, 1)
if ($free -lt 4) {
    Write-Host "  [warn]    only $free GB free on the system drive, the model needs up to 3.1 GB" -ForegroundColor Yellow
} else {
    Write-Host "  [ok]      free space: $free GB" -ForegroundColor Green
}

if ($env:HF_HUB_DISABLE_XET -ne "1") {
    Write-Host ""
    Write-Host "  [warn] HF_HUB_DISABLE_XET is not set. Without it the model download can stall." -ForegroundColor Yellow
    Write-Host "         Fix: [Environment]::SetEnvironmentVariable('HF_HUB_DISABLE_XET','1','User')" -ForegroundColor Yellow
}

Write-Host ""
if ($missing.Count -gt 0) {
    Write-Host "Missing: $($missing -join ', ')" -ForegroundColor Yellow
    Write-Host "Install them per INSTALL.md, or just start the skill and Claude will offer to do it." -ForegroundColor Yellow
} else {
    Write-Host "Everything is in place." -ForegroundColor Green
}
Write-Host ""
Write-Host "Open Claude Code in the folder with your footage and run:" -ForegroundColor Cyan
Write-Host "  /videoediting edit IMG_1234.MOV for Reels" -ForegroundColor White
Write-Host ""
