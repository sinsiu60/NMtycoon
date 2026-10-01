@echo off
rem Factory Tycoon launcher: creates .venv on first run, then starts the game.
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo [1/2] Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo Python was not found. Install Python 3.12 from python.org and check "Add python.exe to PATH".
        pause
        exit /b 1
    )
    echo [2/2] Installing packages...
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo Package install failed. Check your internet connection.
        pause
        exit /b 1
    )
)
".venv\Scripts\python.exe" main.py %*
if errorlevel 1 pause
