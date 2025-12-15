@echo off
cd /d %~dp0
echo.
echo ============================================================
echo    Chatterbox TTS Server - Launcher
echo ============================================================
echo.
python start.py
if errorlevel 1 (
    echo.
    echo [ERROR] Failed to start. Please check the output above.
    echo.
)
pause