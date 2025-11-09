@echo off
REM PyCLIDE Build Script for Windows
REM Creates standalone executable using PyInstaller

setlocal enabledelayedexpansion

echo ╔══════════════════════════════════════════════════════════╗
echo ║           PyCLIDE Standalone Binary Builder             ║
echo ╚══════════════════════════════════════════════════════════╝
echo.

REM Determine script directory
set SCRIPT_DIR=%~dp0
if "%SCRIPT_DIR:~-1%"=="\" set SCRIPT_DIR=%SCRIPT_DIR:~0,-1%

REM Determine project root
for %%I in ("%SCRIPT_DIR%") do set PROJECT_ROOT=%%~dpI
if "%PROJECT_ROOT:~-1%"=="\" set PROJECT_ROOT=%PROJECT_ROOT:~0,-1%

set SCRIPTS_DIR=%PROJECT_ROOT%\scripts
set BIN_DIR=%PROJECT_ROOT%\bin

echo Platform detected: Windows
echo Output binary: pyclide.exe
echo.

REM Check Python
where python >nul 2>&1
if errorlevel 1 (
    echo Error: python not found. Please install Python 3.8+
    exit /b 1
)

for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYTHON_VERSION=%%v
echo Python version: %PYTHON_VERSION%

REM Check dependencies
echo.
echo Checking dependencies...

set MISSING_DEPS=

python -c "import typer" >nul 2>&1
if errorlevel 1 set MISSING_DEPS=%MISSING_DEPS% typer[all]

python -c "import jedi" >nul 2>&1
if errorlevel 1 set MISSING_DEPS=%MISSING_DEPS% jedi

python -c "import rope" >nul 2>&1
if errorlevel 1 set MISSING_DEPS=%MISSING_DEPS% rope

python -c "import PyInstaller" >nul 2>&1
if errorlevel 1 set MISSING_DEPS=%MISSING_DEPS% pyinstaller

if not "%MISSING_DEPS%"=="" (
    echo Missing dependencies:%MISSING_DEPS%
    echo.
    echo Install with:
    echo   pip install%MISSING_DEPS%
    exit /b 1
)

echo ✓ All dependencies installed
echo.

REM Create bin directory if it doesn't exist
if not exist "%BIN_DIR%" mkdir "%BIN_DIR%"

REM Build with PyInstaller
echo Building standalone binary...
echo.

cd /d "%SCRIPTS_DIR%"

pyinstaller ^
    --onefile ^
    --name pyclide.exe ^
    --distpath "%BIN_DIR%" ^
    --workpath "%PROJECT_ROOT%\build\work" ^
    --specpath "%PROJECT_ROOT%\build" ^
    --clean ^
    pyclide.py

echo.
echo ╔══════════════════════════════════════════════════════════╗
echo ║                   Build Successful!                      ║
echo ╚══════════════════════════════════════════════════════════╝
echo.
echo Binary location: %BIN_DIR%\pyclide.exe
echo.

REM Get binary size
if exist "%BIN_DIR%\pyclide.exe" (
    for %%A in ("%BIN_DIR%\pyclide.exe") do set SIZE=%%~zA
    set /a SIZE_MB=!SIZE! / 1048576
    echo Binary size: !SIZE_MB! MB
    echo.
)

echo Test the binary:
echo   %BIN_DIR%\pyclide.exe --version
echo.

echo Note: To build for Linux/macOS, run build.sh on those platforms.
echo.
echo After building for all platforms, you can distribute the plugin with:
echo   - bin\pyclide.exe (Windows)
echo   - bin\pyclide-linux (Linux)
echo   - bin\pyclide-macos (macOS)

endlocal
