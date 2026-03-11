@echo off
REM Startup script for Archie (Windows)
REM Starts both backend and frontend servers

echo 🚀 Starting Archie...
echo.

REM Check if .env.local files exist
if not exist "backend\.env.local" (
    echo ❌ Error: backend\.env.local not found
    echo Please create it from backend\.env.example
    exit /b 1
)

if not exist "frontend\.env.local" (
    echo ❌ Error: frontend\.env.local not found
    echo Please create it from frontend\.env.example
    exit /b 1
)

REM Start Backend
echo 📦 Starting backend server...
cd backend

REM Check if virtual environment exists
if not exist ".venv" (
    echo ⚠️  Virtual environment not found. Creating...
    python -m venv .venv
    call .venv\Scripts\activate.bat
    pip install --upgrade pip
    pip install -r requirements.txt
) else (
    call .venv\Scripts\activate.bat
)

REM Start backend in new window
start "Backend Server" cmd /k "python src\main.py"

REM Check if Redis is available and start worker if so
redis-cli ping >nul 2>&1
if %ERRORLEVEL% == 0 (
    echo 👷 Starting ARQ worker...
    set PYTHONPATH=%CD%\src;%PYTHONPATH%
    start "ARQ Worker" cmd /k "python -m arq workers.tasks.WorkerSettings"
) else (
    echo ℹ️  Redis not available — analysis will run in-process
)
cd ..

timeout /t 2 /nobreak >nul

echo ✅ Backend running on http://localhost:8000
echo.

REM Start Frontend
echo 📦 Starting frontend server...
cd frontend

REM Check if node_modules exists
if not exist "node_modules" (
    echo ⚠️  Node modules not found. Installing...
    call npm install
)

REM Start frontend in new window
start "Frontend Server" cmd /k "npm run dev"
cd ..

timeout /t 3 /nobreak >nul

echo ✅ Frontend server started
echo.
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo ✨ Archie is running!
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo Backend:  http://localhost:8000
echo Frontend: http://localhost:4000
echo API Docs: http://localhost:8000/docs
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo.
echo Both servers are running in separate windows.
echo Close those windows to stop the servers.
echo.

pause
