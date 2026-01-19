@echo off
echo ================================================================================
echo Lab Management System - Starting...
echo ================================================================================

cd /d "%~dp0"

:: Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python from https://python.org
    pause
    exit /b 1
)

:: Check if venv exists, if not create it
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

:: Activate venv and install dependencies
call venv\Scripts\activate.bat

:: Install dependencies if needed
pip show flask >nul 2>&1
if errorlevel 1 (
    echo Installing dependencies...
    pip install -r requirements.txt
)

:: Run the application
echo.
echo Starting server at http://localhost:5000
echo Press Ctrl+C to stop
echo.
python app.py

pause
