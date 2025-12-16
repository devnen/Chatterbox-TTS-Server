@echo off
REM ============================================================================
REM Chatterbox TTS Server - Windows Launcher
REM ============================================================================
REM Double-click this file to start the Chatterbox TTS Server.
REM This script finds Python and runs start.py with all arguments.
REM The window will stay open on errors so you can read the output.
REM ============================================================================
setlocal enabledelayedexpansion

REM Change to the directory where this batch file is located
cd /d "%~dp0"

echo.
echo ============================================================
echo    Chatterbox TTS Server - Launcher
echo ============================================================
echo.

REM Check if start.py exists
if not exist "start.py" (
    echo.
    echo [ERROR] start.py not found!
    echo.
    echo Please make sure start.py is in the same folder as this batch file.
    echo Current directory: %cd%
    echo.
    goto :pause_and_exit
)

REM ============================================================================
REM Find Python Installation
REM ============================================================================
echo Checking for Python installation...
echo.

set PYTHON_CMD=
set PYTHON_FOUND=0

REM Try python3 first (common on systems with multiple Python versions)
python3 --version >nul 2>&1
if %errorlevel% equ 0 (
    for /f "tokens=*" %%i in ('python3 --version 2^>^&1') do set PYTHON_VERSION=%%i
    echo [OK] Found !PYTHON_VERSION! ^(python3^)
    set PYTHON_CMD=python3
    set PYTHON_FOUND=1
    goto :check_version
)

REM Try python command
python --version >nul 2>&1
if %errorlevel% equ 0 (
    for /f "tokens=*" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
    echo [OK] Found !PYTHON_VERSION! ^(python^)
    
    REM Check if it's Python 3.x
    echo !PYTHON_VERSION! | findstr /C:"Python 3." >nul
    if !errorlevel! equ 0 (
        set PYTHON_CMD=python
        set PYTHON_FOUND=1
        goto :check_version
    ) else (
        echo [WARNING] Found Python 2.x, looking for Python 3...
    )
)

REM Try py launcher (Windows Python Launcher)
py --version >nul 2>&1
if %errorlevel% equ 0 (
    REM Try to get Python 3.12 specifically
    py -3.12 --version >nul 2>&1
    if !errorlevel! equ 0 (
        for /f "tokens=*" %%i in ('py -3.12 --version 2^>^&1') do set PYTHON_VERSION=%%i
        echo [OK] Found !PYTHON_VERSION! ^(py -3.12^)
        set PYTHON_CMD=py -3.12
        set PYTHON_FOUND=1
        goto :check_version
    )
    
    REM Try Python 3.11
    py -3.11 --version >nul 2>&1
    if !errorlevel! equ 0 (
        for /f "tokens=*" %%i in ('py -3.11 --version 2^>^&1') do set PYTHON_VERSION=%%i
        echo [OK] Found !PYTHON_VERSION! ^(py -3.11^)
        set PYTHON_CMD=py -3.11
        set PYTHON_FOUND=1
        goto :check_version
    )
    
    REM Try Python 3.10
    py -3.10 --version >nul 2>&1
    if !errorlevel! equ 0 (
        for /f "tokens=*" %%i in ('py -3.10 --version 2^>^&1') do set PYTHON_VERSION=%%i
        echo [OK] Found !PYTHON_VERSION! ^(py -3.10^)
        set PYTHON_CMD=py -3.10
        set PYTHON_FOUND=1
        goto :check_version
    )
    
    REM Fall back to any Python 3
    py -3 --version >nul 2>&1
    if !errorlevel! equ 0 (
        for /f "tokens=*" %%i in ('py -3 --version 2^>^&1') do set PYTHON_VERSION=%%i
        echo [OK] Found !PYTHON_VERSION! ^(py -3^)
        set PYTHON_CMD=py -3
        set PYTHON_FOUND=1
        goto :check_version
    )
)

REM If we get here, Python was not found
if %PYTHON_FOUND% equ 0 (
    echo.
    echo ============================================================
    echo [ERROR] Python 3.10+ not found!
    echo ============================================================
    echo.
    echo Please install Python 3.10 or newer from:
    echo   https://www.python.org/downloads/
    echo.
    echo During installation, make sure to:
    echo   [x] Check "Add Python to PATH"
    echo   [x] Check "Install for all users" ^(recommended^)
    echo.
    echo After installing Python, close this window and try again.
    echo.
    goto :pause_and_exit
)

:check_version
REM ============================================================================
REM Verify Python version is 3.10+
REM ============================================================================
echo.
echo Verifying Python version...

REM Extract major and minor version numbers
for /f "tokens=2 delims= " %%a in ('!PYTHON_CMD! --version 2^>^&1') do set FULL_VERSION=%%a
for /f "tokens=1,2 delims=." %%a in ("!FULL_VERSION!") do (
    set MAJOR=%%a
    set MINOR=%%b
)

REM Check if version is at least 3.10
if !MAJOR! LSS 3 (
    echo [ERROR] Python 3.10+ required, but found Python !MAJOR!.!MINOR!
    goto :version_error
)
if !MAJOR! EQU 3 if !MINOR! LSS 10 (
    echo [ERROR] Python 3.10+ required, but found Python !MAJOR!.!MINOR!
    goto :version_error
)

echo [OK] Python !MAJOR!.!MINOR! meets requirements ^(3.10+^)
goto :run_script

:version_error
echo.
echo ============================================================
echo [ERROR] Python version too old!
echo ============================================================
echo.
echo Chatterbox TTS Server requires Python 3.10 or newer.
echo Found: Python !MAJOR!.!MINOR!
echo.
echo Please install Python 3.10+ from:
echo   https://www.python.org/downloads/
echo.
goto :pause_and_exit

:run_script
REM ============================================================================
REM Run the main Python script
REM ============================================================================
echo.
echo ============================================================
echo Starting Chatterbox TTS Server...
echo ============================================================
echo.
echo Using: !PYTHON_CMD!
echo.

REM Launch Python script with all arguments and wait for it to finish
!PYTHON_CMD! start.py --verbose %*

REM Capture the exit code from Python
set EXIT_CODE=%errorlevel%

REM Show result message based on exit code
echo.
echo ============================================================
if %EXIT_CODE% equ 0 (
    echo Server stopped normally.
) else if %EXIT_CODE% equ 1 (
    echo Server exited with an error ^(code: %EXIT_CODE%^)
) else if %EXIT_CODE% equ 2 (
    echo Installation was cancelled.
) else (
    echo Server exited with code: %EXIT_CODE%
)
echo ============================================================

:pause_and_exit
REM Always pause so the user can read any messages
echo.
echo Press any key to close this window...
pause >nul
endlocal
exit /b %EXIT_CODE%
