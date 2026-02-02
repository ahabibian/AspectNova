@echo off
setlocal enabledelayedexpansion

REM --- Always run from this bat's folder ---
cd /d "%~dp0"

REM --- Paths (adjust if your folders are different) ---
set RAW=SharedData\scan_payload.json
set OUT=SharedData\scan_payload.with_kpis.json

echo.
echo [1/3] Checking Python...
python --version
if errorlevel 1 (
  echo ERROR: Python not found in PATH.
  exit /b 1
)

echo.
echo [2/3] Looking for raw payload: "%RAW%"
if not exist "%RAW%" (
  echo ERROR: Raw payload not found at "%RAW%"
  echo Tip: run these to locate it:
  echo   dir /s /b scan_payload*.json
  exit /b 1
)

echo.
echo [3/3] Building KPIs -> "%OUT%"
python payload_builder_kpis.py "%RAW%" "%OUT%"
if errorlevel 1 (
  echo ERROR: KPI builder failed.
  exit /b 1
)

echo.
echo DONE.
echo Output:
echo   %OUT%
echo.
pause
