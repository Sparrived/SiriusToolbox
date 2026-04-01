@echo off
setlocal
set SCRIPT_DIR=%~dp0
powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%scripts\bootstrap-webui.ps1" %*
if errorlevel 1 (
    echo.
    echo [SiriusToolbox] Startup failed.
    pause
)
endlocal
