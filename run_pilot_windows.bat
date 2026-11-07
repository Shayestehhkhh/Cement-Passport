@echo off
REM Double-click this file (Windows). Requires Python 3.9+ from python.org ("Add python.exe to PATH" ticked).
REM Creates a private Python environment in the folder ".venv" (nothing is installed system-wide).
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Creating a private Python environment - first run only...
  python -m venv .venv
  if errorlevel 1 (
    echo Python was not found. Install it from https://www.python.org/downloads/ and tick "Add python.exe to PATH".
    pause
    exit /b 1
  )
)
echo Installing the two required libraries...
".venv\Scripts\python.exe" -m pip install -q -r requirements.txt
echo.
echo ===== Running the pilot =====
".venv\Scripts\python.exe" src\run_pilot.py
echo.
echo ===== Running the automated tests =====
".venv\Scripts\python.exe" -m unittest discover -s tests -v
echo.
echo Done. The QR code and the log are in the "output" folder.
pause
