@echo off
REM Architecture MCP Server Startup Script for Windows

setlocal enabledelayedexpansion

echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo   Architecture MCP Server
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo.

REM Get script directory
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

REM Check Python
echo Checking Python version...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH
    exit /b 1
)
for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYTHON_VERSION=%%v
echo [OK] Python %PYTHON_VERSION% found

REM Check virtual environment
if not exist ".venv" (
    echo Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment
        exit /b 1
    )
    echo [OK] Virtual environment created
) else (
    echo [OK] Virtual environment found
)

REM Activate virtual environment
echo Activating virtual environment...
call .venv\Scripts\activate.bat
if errorlevel 1 (
    echo [ERROR] Failed to activate virtual environment
    exit /b 1
)
echo [OK] Virtual environment activated

REM Check dependencies
echo Checking dependencies...
python -c "import mcp" >nul 2>&1
if errorlevel 1 (
    echo Installing dependencies...
    python -m pip install --upgrade pip -q
    python -m pip install -r requirements.txt -q
    if errorlevel 1 (
        echo [ERROR] Failed to install dependencies
        exit /b 1
    )
    echo [OK] Dependencies installed
) else (
    echo [OK] Dependencies already installed
)

REM Check DOCS
if not exist "DOCS" (
    echo [ERROR] DOCS directory not found
    exit /b 1
)
if not exist "DOCS\backend" (
    echo [ERROR] DOCS\backend directory not found
    exit /b 1
)
if not exist "DOCS\frontend" (
    echo [ERROR] DOCS\frontend directory not found
    exit /b 1
)
echo [OK] Documentation found
echo.

REM Display server info
echo Server Configuration:
echo   Working Directory: %SCRIPT_DIR%
python --version
echo   MCP Server: architecture-blueprints
echo.

REM Print integration guide
echo.
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo   Cursor MCP Integration
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo.
echo Add this configuration to your Cursor MCP settings:
echo.

REM Get absolute paths
for %%I in ("%SCRIPT_DIR%") do set "SCRIPT_DIR_ABS=%%~fI"
for %%I in (".venv\Scripts\python.exe") do set "PYTHON_PATH=%%~fI"
for %%I in ("%SCRIPT_DIR_ABS%\run_server.py") do set "RUN_SERVER_PATH=%%~fI"

echo {
echo   "mcpServers": {
echo     "architecture": {
echo       "command": "%PYTHON_PATH%",
echo       "args": ["%RUN_SERVER_PATH%"],
echo       "cwd": "%SCRIPT_DIR_ABS%"
echo     }
echo   }
echo }

echo.
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo.

REM Start server
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo   Starting MCP Server...
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo.

python -m src.server

