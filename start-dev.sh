#!/bin/bash

# Legacy startup script — use ./run instead.
# This wrapper exists so existing instructions/muscle-memory still work.

echo -e "\033[1;33m  Tip: use ./run instead — it handles setup + startup in one step.\033[0m"
echo ""
exec "$(dirname "$0")/run" "$@"

# ── Original script below (kept for reference, no longer executes) ──────────

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Starting Repository Analysis System...${NC}\n"

# ── Helper: run a command with a timeout (macOS lacks `timeout`) ──────────
run_with_timeout() {
    local secs="$1"; shift
    "$@" &
    local pid=$!
    local elapsed=0
    while kill -0 "$pid" 2>/dev/null; do
        sleep 1
        elapsed=$((elapsed + 1))
        if [ "$elapsed" -ge "$secs" ]; then
            kill "$pid" 2>/dev/null
            wait "$pid" 2>/dev/null || true
            return 124
        fi
    done
    wait "$pid"
    return $?
}

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

# ── Read DB_BACKEND and REDIS_URL from .env.local ────────────────────────
DB_BACKEND=$(grep -E '^DB_BACKEND=' backend/.env.local 2>/dev/null | cut -d= -f2 | tr -d '[:space:]"'"'" || echo "supabase")
DB_BACKEND=${DB_BACKEND:-supabase}

REDIS_URL=$(grep -E '^REDIS_URL=' backend/.env.local 2>/dev/null | cut -d= -f2 | tr -d '[:space:]"'"'" || echo "")
REDIS_URL=${REDIS_URL:-redis://localhost:6379}

# Parse host and port from REDIS_URL (redis://host:port or redis://host)
REDIS_HOST=$(echo "$REDIS_URL" | sed -E 's|^redis://([^:/]+).*|\1|')
REDIS_PORT=$(echo "$REDIS_URL" | sed -E 's|^redis://[^:]+:([0-9]+).*|\1|')
# If port extraction failed (no port in URL), default to 6379
if [ "$REDIS_PORT" = "$REDIS_URL" ] || [ -z "$REDIS_PORT" ]; then
    REDIS_PORT=6379
fi

# Check if Redis is reachable
check_redis() {
    if command -v redis-cli &>/dev/null; then
        redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" ping &>/dev/null 2>&1
        return $?
    fi
    # No redis-cli available, try a TCP connection
    (echo > /dev/tcp/"$REDIS_HOST"/"$REDIS_PORT") &>/dev/null 2>&1
    return $?
}

# ── Start Docker containers if using local PostgreSQL ────────────────────
if [ "$DB_BACKEND" = "postgres" ]; then
    if ! command -v docker &>/dev/null; then
        echo -e "${RED}❌ Error: DB_BACKEND=postgres but Docker is not installed${NC}"
        echo "Install Docker Desktop from https://www.docker.com/products/docker-desktop/"
        exit 1
    fi

    # Resolve compose command: "docker compose" (plugin) or "docker-compose" (standalone)
    DOCKER_COMPOSE=""
    if run_with_timeout 10 docker compose version &>/dev/null; then
        DOCKER_COMPOSE="docker compose"
    elif command -v docker-compose &>/dev/null; then
        DOCKER_COMPOSE="docker-compose"
    else
        echo -e "${RED}❌ Error: Neither 'docker compose' nor 'docker-compose' is available${NC}"
        echo "Install it with: brew install docker-compose"
        exit 1
    fi

    echo -e "${BLUE}🐘 DB_BACKEND=postgres — starting Docker containers...${NC}"
    COMPOSE_OUTPUT=$($DOCKER_COMPOSE up -d 2>&1) || {
        echo "$COMPOSE_OUTPUT"
        if echo "$COMPOSE_OUTPUT" | grep -qiE "connection refused|timeout|no such host|network|dial tcp|TLS handshake"; then
            echo -e "${RED}❌ Network error pulling Docker images${NC}"
            if colima status &>/dev/null 2>&1; then
                echo -e "${YELLOW}⚠️  Restarting Colima to fix networking...${NC}"
                colima stop 2>/dev/null || true
                sleep 2
                colima start --memory 4 --cpu 2 2>&1 || true
                sleep 3
                echo -e "${BLUE}🔄 Retrying...${NC}"
                $DOCKER_COMPOSE up -d || { echo -e "${RED}❌ Still failing — check your internet connection${NC}"; exit 1; }
            else
                echo "Check your internet connection or VPN and try again."
                exit 1
            fi
        else
            echo -e "${RED}❌ Failed to start Docker containers${NC}"
            exit 1
        fi
    }

    echo -e "${BLUE}⏳ Waiting for PostgreSQL to be ready...${NC}"
    for i in $(seq 1 30); do
        if $DOCKER_COMPOSE exec -T postgres pg_isready -U postgres >/dev/null 2>&1; then
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
    # Ensure all requirements are up to date (including newly added packages)
    pip install -q -r requirements.txt || true
fi

# Read backend port from settings (PORT env var, default 8000)
BACKEND_PORT=$(grep -E '^PORT=' .env.local 2>/dev/null | cut -d= -f2 | tr -d '[:space:]"'"'" || echo "")
BACKEND_PORT=${BACKEND_PORT:-8000}

# Check if prompts/schema version is stale
PROMPTS_VERSION=$(python -c "import json; print(json.load(open('prompts.json'))['version'])" 2>/dev/null || echo "")
SYNCED_VERSION=$(cat .prompts-version 2>/dev/null || echo "")
if [ -n "$PROMPTS_VERSION" ] && [ "$PROMPTS_VERSION" != "$SYNCED_VERSION" ]; then
    echo -e "${RED}⚠️  Updates available (v${SYNCED_VERSION:-old} → v${PROMPTS_VERSION}). Run: ./setup.sh${NC}"
    echo -e "${RED}Cannot start — database schema or prompts are incompatible. Run ./setup.sh first.${NC}"
    exit 1
fi

# ── Validate .env.local for stale/missing keys ──────────────────────────
# Known removed keys that old .env.local files may still contain
STALE_KEYS="VECTOR_DB_TYPE STORAGE_TYPE MAX_ANALYSIS_WORKERS RAG_ENABLED EMBEDDING_PROVIDER OPENAI_API_KEY"
HAS_STALE=false
for KEY in $STALE_KEYS; do
    if grep -qE "^${KEY}=" .env.local 2>/dev/null; then
        if [ "$HAS_STALE" = false ]; then
            echo -e "${YELLOW}⚠️  Your .env.local contains outdated variables:${NC}"
            HAS_STALE=true
        fi
        echo -e "${YELLOW}   - ${KEY} (no longer used — safe to remove)${NC}"
    fi
done
if [ "$HAS_STALE" = true ]; then
    echo -e "${YELLOW}   These won't cause errors but should be cleaned up.${NC}"
    echo ""
fi

# Check required keys
MISSING_REQUIRED=false
if ! grep -qE '^ANTHROPIC_API_KEY=.+' .env.local 2>/dev/null; then
    echo -e "${RED}❌ ANTHROPIC_API_KEY is missing or empty in .env.local${NC}"
    MISSING_REQUIRED=true
fi
if [ "$DB_BACKEND" = "postgres" ]; then
    if ! grep -qE '^DATABASE_URL=.+' .env.local 2>/dev/null; then
        echo -e "${RED}❌ DATABASE_URL is missing or empty (required for DB_BACKEND=postgres)${NC}"
        MISSING_REQUIRED=true
    fi
elif [ "$DB_BACKEND" = "supabase" ]; then
    if ! grep -qE '^SUPABASE_URL=.+' .env.local 2>/dev/null; then
        echo -e "${RED}❌ SUPABASE_URL is missing or empty (required for DB_BACKEND=supabase)${NC}"
        MISSING_REQUIRED=true
    fi
    if ! grep -qE '^SUPABASE_KEY=.+' .env.local 2>/dev/null; then
        echo -e "${RED}❌ SUPABASE_KEY is missing or empty (required for DB_BACKEND=supabase)${NC}"
        MISSING_REQUIRED=true
    fi
fi
if [ "$MISSING_REQUIRED" = true ]; then
    echo -e "${RED}Fix the above in backend/.env.local, or run ./setup.sh to regenerate.${NC}"
    exit 1
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
    if ! command -v redis-cli &>/dev/null && ! (echo > /dev/tcp/"$REDIS_HOST"/"$REDIS_PORT") &>/dev/null 2>&1; then
        ANALYSIS_REASON="redis-cli not found and ${REDIS_HOST}:${REDIS_PORT} not reachable"
    elif command -v redis-cli &>/dev/null; then
        ANALYSIS_REASON="redis-cli ping failed on ${REDIS_HOST}:${REDIS_PORT} (Redis not running?)"
    else
        ANALYSIS_REASON="could not connect to ${REDIS_HOST}:${REDIS_PORT}"
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

echo -e "${GREEN}✅ Backend running on http://localhost:${BACKEND_PORT} (PID: $BACKEND_PID)${NC}"
if [ -n "$WORKER_PID" ] && kill -0 $WORKER_PID 2>/dev/null; then
    echo -e "${GREEN}✅ Worker running (PID: $WORKER_PID)${NC}"
fi
echo ""

# Start Frontend
echo -e "${BLUE}📦 Starting frontend server...${NC}"
cd frontend

# Ensure all dependencies are up to date (catches newly added packages)
if [ ! -d "node_modules" ]; then
    echo -e "${YELLOW}⚠️  Node modules not found. Installing...${NC}"
    npm install
else
    # Run npm install to catch new dependencies but allow continuing if it fails (offline mode)
    npm install --silent || true
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
echo -e "${BLUE}Backend:${NC}  http://localhost:${BACKEND_PORT}"
echo -e "${BLUE}Frontend:${NC} http://localhost:${FRONTEND_PORT}"
echo -e "${BLUE}API Docs:${NC} http://localhost:${BACKEND_PORT}/docs"
if [ "$DB_BACKEND" = "postgres" ]; then
    echo -e "${BLUE}Database:${NC} Local PostgreSQL (Docker)"
else
    echo -e "${BLUE}Database:${NC} Supabase (remote)"
fi
if [ "$ANALYSIS_MODE" = "arq" ]; then
    echo -e "${BLUE}Redis:${NC}    ${REDIS_URL}"
    echo -e "${BLUE}Analysis:${NC} ARQ worker (Redis-backed background jobs)"
else
    echo -e "${BLUE}Redis:${NC}    Not connected (${REDIS_URL})"
    echo -e "${BLUE}Analysis:${NC} In-process (running inside FastAPI server)"
fi
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}Press Ctrl+C to stop both servers${NC}\n"

# Wait for both processes
wait $BACKEND_PID $FRONTEND_PID

