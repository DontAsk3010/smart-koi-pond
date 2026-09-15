@echo off
setlocal
cd /d "%~dp0"

title Smart Koi Pond - Virtual Pond Launcher

echo.
echo SMART KOI POND - VIRTUAL POND
echo SIMULATION / NO REAL DEVICE CONTROL
echo.

where py >nul 2>nul
if %errorlevel%==0 (
    set "PY_CMD=py"
) else (
    where python >nul 2>nul
    if %errorlevel%==0 (
        set "PY_CMD=python"
    ) else (
        echo Python was not found on this Windows computer.
        echo The Virtual Pond source is ready, but a local Python 3.11+ runtime is required to run it locally.
        echo Online deployment will not require Python to be installed on this computer.
        echo.
        pause
        exit /b 1
    )
)

if not exist "runtime-data" mkdir "runtime-data"

set "PYTHONPATH=%CD%\src"
set "SMART_KOI_HOST=127.0.0.1"
set "SMART_KOI_PORT=8080"
set "SMART_KOI_HISTORIAN_PATH=%CD%\runtime-data\historian.jsonl"

start "" powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 2; Start-Process 'http://127.0.0.1:8080'"

echo Starting Virtual Pond at http://127.0.0.1:8080
echo Keep this window open while using Virtual Pond.
echo Close this window or press Ctrl+C to stop the local runtime.
echo.

%PY_CMD% -m smart_koi_pond.dashboard.app

if errorlevel 1 (
    echo.
    echo Virtual Pond stopped with an error.
    pause
)
