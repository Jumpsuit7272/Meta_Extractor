@echo off
REM RPD Meta Extractor - Server installation and run script for Windows
REM Usage: install_and_run.bat [port]
REM Bind to 0.0.0.0 for intranet access (accessible from other machines on the network)

cd /d "%~dp0\.."

set PORT=%1
if "%PORT%"=="" set PORT=8000

set HOST=0.0.0.0

echo === RPD Meta Extractor - Server Setup ===
echo Directory: %CD%
echo Host: %HOST% (0.0.0.0 = all interfaces / intranet^)
echo Port: %PORT%
echo.

REM Create virtual environment if it doesn't exist
if not exist "venv\" (
    echo Creating virtual environment...
    python -m venv venv
)

echo Activating virtual environment...
call venv\Scripts\activate.bat

echo Installing/upgrading dependencies...
python -m pip install -q -U pip
pip install -q -r requirements.txt

echo.
echo === Starting RPD Meta Extractor ===
echo   App UI:    http://localhost:%PORT%
echo   Intranet:  http://%COMPUTERNAME%:%PORT%
echo   API Docs:  http://localhost:%PORT%/docs
echo   Health:    http://localhost:%PORT%/health
echo.
echo Press Ctrl+C to stop.
echo.

set RPD_HOST=%HOST%
set RPD_PORT=%PORT%
python -m uvicorn rpd.main:app --host %HOST% --port %PORT%
