@echo off
REM PyCLIDE Wrapper Script for Windows
REM Automatically calls the Windows binary and forwards all arguments.

setlocal

REM Determine the script directory (where this wrapper is located)
set SCRIPT_DIR=%~dp0

REM Remove trailing backslash from SCRIPT_DIR
if "%SCRIPT_DIR:~-1%"=="\" set SCRIPT_DIR=%SCRIPT_DIR:~0,-1%

REM Determine plugin root (parent of scripts\)
for %%I in ("%SCRIPT_DIR%") do set PLUGIN_ROOT=%%~dpI

REM Remove trailing backslash from PLUGIN_ROOT
if "%PLUGIN_ROOT:~-1%"=="\" set PLUGIN_ROOT=%PLUGIN_ROOT:~0,-1%

REM Use CLAUDE_PLUGIN_ROOT if available
if not "%CLAUDE_PLUGIN_ROOT%"=="" set PLUGIN_ROOT=%CLAUDE_PLUGIN_ROOT%

REM Set binary path
set BINARY=%PLUGIN_ROOT%\bin\pyclide.exe

REM Check if binary exists
if not exist "%BINARY%" (
    echo Error: PyCLIDE binary not found: %BINARY% 1>&2
    echo Please build the binary using: %PLUGIN_ROOT%\build\build.bat 1>&2
    exit /b 1
)

REM Execute binary with all arguments forwarded
"%BINARY%" %*
