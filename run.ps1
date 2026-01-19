# Lab Management System - PowerShell Launcher
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "Lab Management System - Starting..." -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan

Set-Location $PSScriptRoot

# Check if Python is available
try {
    $pythonVersion = python --version 2>&1
    Write-Host "Found $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Python is not installed or not in PATH" -ForegroundColor Red
    Write-Host "Please install Python from https://python.org" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

# Check if venv exists, if not create it
if (-not (Test-Path "venv")) {
    Write-Host "Creating virtual environment..." -ForegroundColor Yellow
    python -m venv venv
}

# Activate venv
& ".\venv\Scripts\Activate.ps1"

# Install dependencies if needed
$flaskInstalled = pip show flask 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installing dependencies..." -ForegroundColor Yellow
    pip install -r requirements.txt
}

# Run the application
Write-Host ""
Write-Host "Starting server at http://localhost:5000" -ForegroundColor Green
Write-Host "Press Ctrl+C to stop" -ForegroundColor Yellow
Write-Host ""

python app.py
