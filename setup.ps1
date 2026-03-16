# =============================================================================
# ADS-B Visual Tracker - Windows 11 Setup Script
# =============================================================================
# Run once after cloning the repository (from an elevated PowerShell prompt):
#   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
#   .\setup.ps1
#
# What this does:
#   1. Verifies Python 3.10+ is installed
#   2. Creates a Python virtualenv and installs Python dependencies
#   3. Installs a Windows Task Scheduler task so the app starts on boot
#   4. Optionally configures Edge to auto-launch in kiosk mode on login
# =============================================================================

#Requires -RunAsAdministrator

$ErrorActionPreference = 'Stop'

$RepoDir     = Split-Path -Parent $MyInvocation.MyCommand.Definition
$VenvDir     = Join-Path $RepoDir 'venv'
$PythonExe   = Join-Path $VenvDir 'Scripts\python.exe'
$PipExe      = Join-Path $VenvDir 'Scripts\pip.exe'
$TaskName    = 'ADSB-Visual-Tracker'
$AppPort     = 5000

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
function Info  { param($m) Write-Host "[INFO]  $m" -ForegroundColor Cyan }
function Ok    { param($m) Write-Host "[ OK ]  $m" -ForegroundColor Green }
function Warn  { param($m) Write-Host "[WARN]  $m" -ForegroundColor Yellow }
function Die   { param($m) Write-Host "[ERR ]  $m" -ForegroundColor Red; exit 1 }

# ---------------------------------------------------------------------------
# 1. Verify Python 3.10+
# ---------------------------------------------------------------------------
Info "Checking Python installation..."

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Die "Python not found. Install Python 3.10+ from https://www.python.org/downloads/ and ensure it is on PATH."
}

$versionOutput = & python --version 2>&1
if ($versionOutput -match 'Python (\d+)\.(\d+)') {
    $major = [int]$Matches[1]
    $minor = [int]$Matches[2]
    if ($major -lt 3 -or ($major -eq 3 -and $minor -lt 10)) {
        Die "Python 3.10 or newer is required. Found: $versionOutput"
    }
    Ok "Found $versionOutput"
} else {
    Die "Could not determine Python version."
}

# ---------------------------------------------------------------------------
# 2. Create virtual environment
# ---------------------------------------------------------------------------
if (Test-Path $VenvDir) {
    Warn "Virtual environment already exists at $VenvDir - skipping creation."
} else {
    Info "Creating virtual environment in $VenvDir..."
    & python -m venv $VenvDir
    Ok "Virtual environment created."
}

# ---------------------------------------------------------------------------
# 3. Install Python dependencies
# ---------------------------------------------------------------------------
Info "Upgrading pip..."
& $PipExe install --upgrade pip -q

Info "Installing Python dependencies from requirements.txt..."
& $PipExe install -r (Join-Path $RepoDir 'requirements.txt') -q
Ok "Python dependencies installed."

# ---------------------------------------------------------------------------
# 4. Windows Task Scheduler - run on boot
# ---------------------------------------------------------------------------
Info "Configuring Windows Task Scheduler task: $TaskName"

$existingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existingTask) {
    Warn "Task '$TaskName' already exists - removing and recreating."
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

$action = New-ScheduledTaskAction `
    -Execute $PythonExe `
    -Argument (Join-Path $RepoDir 'main.py') `
    -WorkingDirectory $RepoDir

$trigger = New-ScheduledTaskTrigger -AtStartup

$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Hours 0) `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -StartWhenAvailable

$principal = New-ScheduledTaskPrincipal `
    -UserId $env:USERNAME `
    -LogonType Interactive `
    -RunLevel Highest

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Description "ADS-B Visual Tracker - starts the Flask/SocketIO server on boot" | Out-Null

Ok "Task '$TaskName' registered. The app will start automatically on next boot."

# Offer to start the task now
$startNow = Read-Host "Start the app now? [y/N]"
if ($startNow -match '^[Yy]$') {
    Start-ScheduledTask -TaskName $TaskName
    Ok "App started. Open http://localhost:$AppPort in your browser."
}

# ---------------------------------------------------------------------------
# 5. Edge kiosk mode autostart (optional)
# ---------------------------------------------------------------------------
$kiosk = Read-Host "Configure Microsoft Edge to auto-launch in kiosk mode on login? [y/N]"
if ($kiosk -match '^[Yy]$') {
    $startupFolder = [System.Environment]::GetFolderPath('Startup')
    $shortcutPath  = Join-Path $startupFolder 'ADSB-Kiosk.lnk'

    $edgePaths = @(
        "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe",
        "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe"
    )
    $edgeExe = $edgePaths | Where-Object { Test-Path $_ } | Select-Object -First 1

    if (-not $edgeExe) {
        Warn "Microsoft Edge not found - skipping kiosk shortcut. Install Edge and re-run if needed."
    } else {
        $wsh      = New-Object -ComObject WScript.Shell
        $shortcut = $wsh.CreateShortcut($shortcutPath)
        $shortcut.TargetPath  = $edgeExe
        $shortcut.Arguments   = "--kiosk http://localhost:$AppPort --edge-kiosk-type=fullscreen --no-first-run"
        $shortcut.Description = "ADS-B Visual Tracker kiosk"
        $shortcut.Save()
        Ok "Edge kiosk shortcut created in Startup folder: $shortcutPath"
    }
}

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
$ip = (Get-NetIPAddress -AddressFamily IPv4 |
       Where-Object { $_.InterfaceAlias -notmatch 'Loopback' } |
       Select-Object -First 1).IPAddress

Write-Host ""
Write-Host "========================================================" -ForegroundColor Cyan
Ok "Setup complete!"
Write-Host ""
Write-Host "  App URL    :  http://localhost:$AppPort"
Write-Host "  Network URL:  http://${ip}:$AppPort"
Write-Host ""
Write-Host "  Task Scheduler:"
Write-Host "    Start : Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "    Stop  : Stop-ScheduledTask  -TaskName '$TaskName'"
Write-Host "    Status: Get-ScheduledTask   -TaskName '$TaskName'"
Write-Host ""
Write-Host "  Pre-cache tiles for offline use:"
Write-Host "    $PythonExe cache_tiles.py --from-config"
Write-Host "========================================================" -ForegroundColor Cyan
