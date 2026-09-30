@echo off
REM PagePilot local Windows build (backup option if you prefer not to use GitHub Actions)
REM Requires: Python 3.11+ installed and on PATH.
python -m pip install --upgrade pip
pip install -r requirements.txt
REM Bundle Chromium next to the app so the EXE is self-contained
set PLAYWRIGHT_BROWSERS_PATH=%CD%\pw-browsers
python -m playwright install chromium
pyinstaller --noconfirm --onedir --windowed --name PagePilot --collect-all playwright --add-data "pagepilot/ui;pagepilot/ui" --add-data "pw-browsers;pw-browsers" main.py
echo.
echo Done. Run: dist\PagePilot\PagePilot.exe
pause
