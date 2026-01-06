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
    echo "Please create it from backend/.env.example"
    exit 1
fi

if [ ! -f "frontend/.env.local" ]; then
    echo -e "${RED}❌ Error: frontend/.env.local not found${NC}"
    echo "Please create it from frontend/.env.example"
    exit 1
fi

# Function to cleanup on exit
cleanup() {
    echo -e "\n${YELLOW}🛑 Shutting down servers...${NC}"
    kill $BACKEND_PID $FRONTEND_PID $WORKER_PID 2>/dev/null || true
    exit 0
}

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
fi

# Start backend in background
python src/main.py &
BACKEND_PID=$!

# Start ARQ worker in background
echo -e "${BLUE}👷 Starting ARQ worker...${NC}"
export PYTHONPATH=$PYTHONPATH:$(pwd)/src
python -m arq workers.tasks.WorkerSettings &
WORKER_PID=$!
cd ..

# Wait a moment for backend to start
sleep 2

# Check if processes started successfully
if ! kill -0 $BACKEND_PID 2>/dev/null; then
    echo -e "${RED}❌ Backend failed to start${NC}"
    exit 1
fi

if ! kill -0 $WORKER_PID 2>/dev/null; then
    echo -e "${RED}❌ Worker failed to start${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Backend running on http://localhost:8000 (PID: $BACKEND_PID)${NC}"
echo -e "${GREEN}✅ Worker running (PID: $WORKER_PID)${NC}\n"

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
FRONTEND_PORT=3000
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
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}Press Ctrl+C to stop both servers${NC}\n"

# Wait for both processes
wait $BACKEND_PID $FRONTEND_PID

