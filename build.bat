@echo off
rem Builds dist\FactoryTycoon\FactoryTycoon.exe (folder build, no console window).
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    python -m venv .venv || (echo Python 3.12 is required & pause & exit /b 1)
)
set PY=.venv\Scripts\python.exe
%PY% -m pip install -r requirements-dev.txt || (pause & exit /b 1)
echo Running tests...
%PY% -m pytest -q tests || (echo Tests failed. & pause & exit /b 1)
echo Generating icon...
%PY% tools\make_icon.py || (pause & exit /b 1)
echo Building exe...
%PY% -m PyInstaller --noconfirm --clean --noconsole --onedir --name FactoryTycoon --icon assets\icon.ico --add-data "data;data" --add-data "assets;assets" main.py || (pause & exit /b 1)
copy /y README.md dist\FactoryTycoon\README.md > nul
echo.
echo Done: dist\FactoryTycoon\FactoryTycoon.exe
echo Zip the whole dist\FactoryTycoon folder to share it.
pause
