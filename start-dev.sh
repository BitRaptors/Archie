#!/bin/bash

# Startup script for Repository Analysis System
# Starts both backend and frontend servers

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Starting Repository Analysis System...${NC}\n"

# Check if .env.local files exist
if [ ! -f "backend/.env.local" ]; then
    echo -e "${RED}❌ Error: backend/.env.local not found${NC}"
    echo "Please run ./setup.sh first, or copy backend/.env.example to backend/.env.local"
    exit 1
fi

if [ ! -f "frontend/.env.local" ]; then
    echo -e "${RED}❌ Error: frontend/.env.local not found${NC}"
    echo "Please run ./setup.sh first, or copy frontend/.env.example to frontend/.env.local"
    exit 1
fi

# Function to cleanup on exit
cleanup() {
    echo -e "\n${YELLOW}🛑 Shutting down servers...${NC}"
    kill $BACKEND_PID $FRONTEND_PID $WORKER_PID 2>/dev/null || true
    exit 0
}

# Check if Redis is reachable
check_redis() {
    if command -v redis-cli &>/dev/null; then
        redis-cli ping &>/dev/null 2>&1
        return $?
    fi
    # No redis-cli available, try a TCP connection
    (echo > /dev/tcp/localhost/6379) &>/dev/null 2>&1
    return $?
}

# ── Read DB_BACKEND from .env.local ──────────────────────────────────────
DB_BACKEND=$(grep -E '^DB_BACKEND=' backend/.env.local 2>/dev/null | cut -d= -f2 | tr -d '[:space:]"'"'" || echo "supabase")
DB_BACKEND=${DB_BACKEND:-supabase}

# ── Start Docker containers if using local PostgreSQL ────────────────────
if [ "$DB_BACKEND" = "postgres" ]; then
    if ! command -v docker &>/dev/null; then
        echo -e "${RED}❌ Error: DB_BACKEND=postgres but Docker is not installed${NC}"
        echo "Install Docker Desktop from https://www.docker.com/products/docker-desktop/"
        exit 1
    fi

    echo -e "${BLUE}🐘 DB_BACKEND=postgres — starting Docker containers...${NC}"
    docker compose up -d

    echo -e "${BLUE}⏳ Waiting for PostgreSQL to be ready...${NC}"
    for i in $(seq 1 30); do
        if docker compose exec -T postgres pg_isready -U postgres >/dev/null 2>&1; then
            echo -e "${GREEN}✅ PostgreSQL is ready${NC}"
            break
        fi
        if [ "$i" -eq 30 ]; then
            echo -e "${RED}❌ PostgreSQL did not become ready in 30s${NC}"
            exit 1
        fi
        sleep 1
    done
else
    echo -e "${BLUE}☁️  DB_BACKEND=supabase — using remote Supabase${NC}"
fi

# Trap Ctrl+C
trap cleanup SIGINT SIGTERM

# Start Backend
echo -e "${BLUE}📦 Starting backend server...${NC}"
cd backend

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo -e "${YELLOW}⚠️  Virtual environment not found. Creating...${NC}"
    python3 -m venv .venv
    source .venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
else
    source .venv/bin/activate
    # Ensure all requirements are up to date (including newly added packages like mcp)
    pip install -q -r requirements.txt 2>/dev/null || true
fi

# Start backend in background
python src/main.py &
BACKEND_PID=$!

# Start ARQ worker only if Redis is available
WORKER_PID=""
ANALYSIS_MODE=""
if check_redis; then
    ANALYSIS_MODE="arq"
    echo -e "${BLUE}👷 Starting ARQ worker (Redis detected)...${NC}"
    export PYTHONPATH=$PYTHONPATH:$(pwd)/src
    python -m workers.worker &
    WORKER_PID=$!
else
    ANALYSIS_MODE="in-process"
    if ! command -v redis-cli &>/dev/null && ! (echo > /dev/tcp/localhost/6379) &>/dev/null 2>&1; then
        ANALYSIS_REASON="redis-cli not found and port 6379 not reachable"
    elif command -v redis-cli &>/dev/null; then
        ANALYSIS_REASON="redis-cli ping failed (Redis not running?)"
    else
        ANALYSIS_REASON="could not connect to localhost:6379"
    fi
    echo -e "${YELLOW}ℹ️  Redis not available — analysis will run in-process${NC}"
    echo -e "${YELLOW}   Reason: ${ANALYSIS_REASON}${NC}"
fi
cd ..

# Wait a moment for backend to start
sleep 2

# Check if processes started successfully
if ! kill -0 $BACKEND_PID 2>/dev/null; then
    echo -e "${RED}❌ Backend failed to start${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Backend running on http://localhost:8000 (PID: $BACKEND_PID)${NC}"
if [ -n "$WORKER_PID" ] && kill -0 $WORKER_PID 2>/dev/null; then
    echo -e "${GREEN}✅ Worker running (PID: $WORKER_PID)${NC}"
fi
echo ""

# Start Frontend
echo -e "${BLUE}📦 Starting frontend server...${NC}"
cd frontend

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo -e "${YELLOW}⚠️  Node modules not found. Installing...${NC}"
    npm install
fi

# Create a temporary file to capture the port
FRONTEND_PORT_FILE=$(mktemp)
FRONTEND_LOG_FILE=$(mktemp)

# Start frontend in background and capture output
npm run dev > "$FRONTEND_LOG_FILE" 2>&1 &
FRONTEND_PID=$!
cd ..

# Wait for Next.js to start and extract the port
FRONTEND_PORT=4000
for i in {1..10}; do
    sleep 1
    # Try to extract port from Next.js output
    PORT_LINE=$(grep -E "Local:\s+http://localhost:[0-9]+" "$FRONTEND_LOG_FILE" 2>/dev/null | head -1)
    if [ -n "$PORT_LINE" ]; then
        FRONTEND_PORT=$(echo "$PORT_LINE" | grep -oE "localhost:[0-9]+" | cut -d: -f2)
        break
    fi
    # Also check for "ready" message
    if grep -q "Ready in" "$FRONTEND_LOG_FILE" 2>/dev/null; then
        # If we see ready but no port line, try to find it in the log
        PORT_LINE=$(grep -E "localhost:[0-9]+" "$FRONTEND_LOG_FILE" 2>/dev/null | head -1)
        if [ -n "$PORT_LINE" ]; then
            FRONTEND_PORT=$(echo "$PORT_LINE" | grep -oE "localhost:[0-9]+" | cut -d: -f2)
            break
        fi
    fi
done

# Clean up temp files
rm -f "$FRONTEND_PORT_FILE"

# Check if frontend started successfully
if ! kill -0 $FRONTEND_PID 2>/dev/null; then
    echo -e "${RED}❌ Frontend failed to start${NC}"
    cat "$FRONTEND_LOG_FILE" 2>/dev/null | tail -20
    rm -f "$FRONTEND_LOG_FILE"
    kill $BACKEND_PID 2>/dev/null || true
    exit 1
fi

echo -e "${GREEN}✅ Frontend running on http://localhost:${FRONTEND_PORT} (PID: $FRONTEND_PID)${NC}\n"

# Clean up log file
rm -f "$FRONTEND_LOG_FILE"

echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✨ Repository Analysis System is running!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Backend:${NC}  http://localhost:8000"
echo -e "${BLUE}Frontend:${NC} http://localhost:${FRONTEND_PORT}"
echo -e "${BLUE}API Docs:${NC} http://localhost:8000/docs"
if [ "$DB_BACKEND" = "postgres" ]; then
    echo -e "${BLUE}Database:${NC} Local PostgreSQL (Docker)"
else
    echo -e "${BLUE}Database:${NC} Supabase (remote)"
fi
if [ "$ANALYSIS_MODE" = "arq" ]; then
    echo -e "${BLUE}Analysis:${NC} ARQ worker (Redis-backed background jobs)"
else
    echo -e "${BLUE}Analysis:${NC} In-process (running inside FastAPI server)"
fi
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}Press Ctrl+C to stop both servers${NC}\n"

# Wait for both processes
wait $BACKEND_PID $FRONTEND_PID

