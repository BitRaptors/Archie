#!/usr/bin/env bash
# Full local development environment setup.
# Installs prerequisites, optionally starts Docker, and generates .env files.
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ── Helper: read a key from an env file (returns empty if missing/blank) ──

env_get() {
    # Usage: env_get FILE KEY
    local val
    val=$(grep -E "^${2}=" "$1" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '[:space:]"'"'" || true)
    echo "$val"
}

# ── Helper: ensure a key exists in an env file; prompt if missing/empty ───

env_ensure() {
    # Usage: env_ensure FILE KEY PROMPT [DEFAULT]
    local file="$1" key="$2" prompt="$3" default="${4:-}"
    local current
    current=$(env_get "$file" "$key")

    if [ -n "$current" ]; then
        return 0  # already set
    fi

    # Prompt user for value (or use default)
    local value="$default"
    if [ -t 0 ] && [ -z "$default" ]; then
        read -rp "$prompt" value
    elif [ -t 0 ] && [ -n "$default" ]; then
        read -rp "${prompt} [${default}]: " value
        value="${value:-$default}"
    fi

    # Append to file
    if grep -qE "^${key}=" "$file" 2>/dev/null; then
        # Key exists but is empty — replace the line
        if [ "$(uname -s)" = "Darwin" ]; then
            sed -i '' "s|^${key}=.*|${key}=${value}|" "$file"
        else
            sed -i "s|^${key}=.*|${key}=${value}|" "$file"
        fi
    elif grep -qE "^# *${key}=" "$file" 2>/dev/null; then
        # Key is commented out — uncomment and set
        if [ "$(uname -s)" = "Darwin" ]; then
            sed -i '' "s|^# *${key}=.*|${key}=${value}|" "$file"
        else
            sed -i "s|^# *${key}=.*|${key}=${value}|" "$file"
        fi
    else
        # Key doesn't exist at all — append
        echo "${key}=${value}" >> "$file"
    fi

    if [ -n "$value" ]; then
        info "Set ${key}"
    else
        warn "${key} is still empty — fill it in later in ${file}"
    fi
}

# ── Determine database backend ────────────────────────────────────────────

ENV_FILE="backend/.env.local"
DB_BACKEND=""
NEEDS_NEW_ENV=false

if [ -f "$ENV_FILE" ]; then
    DB_BACKEND=$(env_get "$ENV_FILE" "DB_BACKEND")
    if [ -z "$DB_BACKEND" ]; then
        # DB_BACKEND missing from existing file — ask
        echo ""
        echo -e "${BLUE}DB_BACKEND not set in ${ENV_FILE}. Which backend?${NC}"
        echo "  1) postgres   2) supabase"
        if [ -t 0 ]; then
            read -rp "Enter 1 or 2 [1]: " DB_CHOICE
            case "${DB_CHOICE:-1}" in
                2|supabase) DB_BACKEND="supabase" ;;
                *)          DB_BACKEND="postgres" ;;
            esac
        else
            DB_BACKEND="postgres"
        fi
        env_ensure "$ENV_FILE" "DB_BACKEND" "" "$DB_BACKEND"
    fi
    info "Found existing ${ENV_FILE} (DB_BACKEND=${DB_BACKEND})"
else
    NEEDS_NEW_ENV=true
    echo ""
    echo -e "${BLUE}Which database backend do you want to use?${NC}"
    echo ""
    echo "  1) postgres   — Local PostgreSQL via Docker (recommended for development)"
    echo "  2) supabase   — Remote Supabase project (requires URL + key)"
    echo ""

    DB_BACKEND="postgres"
    if [ -t 0 ]; then
        read -rp "Enter 1 or 2 [1]: " DB_CHOICE
        case "${DB_CHOICE:-1}" in
            2|supabase) DB_BACKEND="supabase" ;;
            *)          DB_BACKEND="postgres" ;;
        esac
    fi
    info "Database backend: ${DB_BACKEND}"
fi

# ── Platform detection ─────────────────────────────────────────────────────

OS="$(uname -s)"
IS_WSL=false

case "$OS" in
    MINGW*|MSYS*|CYGWIN*)
        echo ""
        echo -e "${RED}This script must be run inside WSL2, not Git Bash or MSYS.${NC}"
        echo ""
        echo "  1. Install WSL2:   wsl --install"
        echo "  2. Open Ubuntu:    wsl"
        echo "  3. Clone & run:    git clone <repo> && cd <repo> && ./setup.sh"
        echo ""
        exit 1
        ;;
    Linux)
        if grep -qi 'microsoft\|wsl' /proc/version 2>/dev/null; then
            IS_WSL=true
            info "Detected WSL2 on Windows"
        fi
        ;;
esac

# ── Prerequisites ──────────────────────────────────────────────────────────

ensure_brew() {
    if [ "$OS" = "Darwin" ] && ! command -v brew &>/dev/null; then
        info "Installing Homebrew..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        if [ -f /opt/homebrew/bin/brew ]; then
            eval "$(/opt/homebrew/bin/brew shellenv)"
        elif [ -f /usr/local/bin/brew ]; then
            eval "$(/usr/local/bin/brew shellenv)"
        fi
    fi
}

# Docker (only required for postgres backend)
if [ "$DB_BACKEND" = "postgres" ]; then
    if [ "$OS" = "Darwin" ]; then
        # macOS: use Colima (lightweight CLI runtime) — no Docker Desktop needed
        ensure_brew

        # Install Docker CLI + Compose plugin (not Docker Desktop)
        if ! command -v docker &>/dev/null; then
            info "Installing Docker CLI..."
            brew install docker docker-compose
        fi

        # Install Colima if no Docker runtime is available
        if ! command -v colima &>/dev/null && ! docker info &>/dev/null 2>&1; then
            info "Installing Colima (lightweight Docker runtime)..."
            brew install colima
        fi

        # Start a Docker runtime
        if ! docker info &>/dev/null 2>&1; then
            if command -v colima &>/dev/null; then
                info "Starting Colima..."
                colima start --memory 4 --cpu 2 2>&1 || true
                # Wait for Colima to be ready
                for i in $(seq 1 30); do
                    if docker info >/dev/null 2>&1; then
                        info "Colima is ready"
                        break
                    fi
                    if [ "$i" -eq 30 ]; then
                        error "Colima did not start in time. Try: colima start"
                    fi
                    sleep 2
                done
            elif [ -d "/Applications/Docker.app" ]; then
                info "Starting Docker Desktop..."
                open -a Docker
                for i in $(seq 1 60); do
                    if docker info >/dev/null 2>&1; then
                        info "Docker Desktop is ready"
                        break
                    fi
                    if [ "$i" -eq 60 ]; then
                        error "Docker daemon did not start in time. Re-run: ./setup.sh"
                    fi
                    printf "\r  Waiting for Docker daemon... %ds" "$((i * 2))"
                    sleep 2
                done
                echo ""
            else
                error "No Docker runtime found. Install Colima: brew install colima"
            fi
        fi

    elif [ "$OS" = "Linux" ]; then
        if ! command -v docker &>/dev/null; then
            info "Installing Docker via official script..."
            curl -fsSL https://get.docker.com | sh
            sudo usermod -aG docker "$USER"
            if [ "$IS_WSL" = false ]; then
                warn "You may need to log out and back in for Docker group permissions to take effect"
            fi
        fi
        if ! docker info &>/dev/null 2>&1; then
            if [ "$IS_WSL" = true ]; then
                # WSL2: systemd may not be available — use service command
                info "Starting Docker daemon (WSL2)..."
                if command -v systemctl &>/dev/null && systemctl is-system-running &>/dev/null 2>&1; then
                    sudo systemctl start docker
                else
                    sudo service docker start
                fi
            else
                info "Starting Docker daemon..."
                sudo systemctl start docker
            fi
            sleep 2
            if ! docker info &>/dev/null 2>&1; then
                if [ "$IS_WSL" = true ]; then
                    error "Docker daemon failed to start. Try: sudo service docker start"
                else
                    error "Docker daemon failed to start. Check: sudo systemctl status docker"
                fi
            fi
        fi
    else
        error "Unsupported OS. Please install Docker manually: https://docs.docker.com/get-docker/"
    fi

    info "Docker $(docker --version | cut -d' ' -f3 | tr -d ',') OK"
else
    info "Skipping Docker (not needed for Supabase backend)"
fi

# Python
if ! command -v python3 &>/dev/null; then
    if [ "$OS" = "Darwin" ]; then
        ensure_brew
        info "Installing Python via Homebrew..."
        brew install python@3.13
    elif [ "$OS" = "Linux" ]; then
        info "Installing Python via apt..."
        sudo apt-get update -qq && sudo apt-get install -y -qq python3 python3-venv python3-pip
    else
        error "Please install Python 3.11+: https://www.python.org/downloads/"
    fi
fi

PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
if python3 -c "import sys; exit(0 if sys.version_info >= (3, 11) else 1)"; then
    info "Python ${PY_VERSION} OK"
else
    error "Python 3.11+ required (found ${PY_VERSION})"
fi

# Node
if ! command -v node &>/dev/null; then
    if [ "$OS" = "Darwin" ]; then
        ensure_brew
        info "Installing Node.js via Homebrew..."
        brew install node
    elif [ "$OS" = "Linux" ]; then
        info "Installing Node.js via NodeSource..."
        curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
        sudo apt-get install -y -qq nodejs
    else
        error "Please install Node.js 18+: https://nodejs.org/"
    fi
fi

NODE_MAJOR=$(node -v | sed 's/v//' | cut -d. -f1)
if [ "$NODE_MAJOR" -ge 18 ]; then
    info "Node $(node -v) OK"
else
    error "Node 18+ required (found $(node -v))"
fi

# ── Docker services (postgres only) ──────────────────────────────────────

if [ "$DB_BACKEND" = "postgres" ]; then
    info "Starting PostgreSQL + Redis via Docker Compose..."
    # Retry docker compose up — prune corrupted images on failure
    for attempt in 1 2 3; do
        if docker compose up -d 2>&1; then
            break
        fi
        if [ "$attempt" -eq 3 ]; then
            error "docker compose up failed after 3 attempts. Try: docker system prune -a --force && ./setup.sh"
        fi
        warn "Docker containers failed to start (attempt ${attempt}/3). Pruning corrupted images..."
        docker system prune -a --force 2>/dev/null || true
        sleep 5
    done

    info "Waiting for PostgreSQL to be ready..."
    for i in $(seq 1 30); do
        if docker compose exec -T postgres pg_isready -U postgres >/dev/null 2>&1; then
            info "PostgreSQL is ready"
            break
        fi
        if [ "$i" -eq 30 ]; then
            error "PostgreSQL did not become ready in 30s"
        fi
        sleep 1
    done

    # Verify migration ran
    ROWS=$(docker compose exec -T postgres psql -U postgres -d architecture_mcp -tAc "SELECT count(*) FROM analysis_prompts" 2>/dev/null || echo "0")
    if [ "${ROWS:-0}" -ge 1 ]; then
        info "Migration verified: ${ROWS} prompts seeded"
    else
        warn "Seed data not detected — migration may need manual review"
    fi
fi

# ── Python backend ─────────────────────────────────────────────────────────

info "Setting up Python backend..."
cd backend

if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    info "Created Python venv"
fi

.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -r requirements.txt
info "Backend dependencies installed"

# ── Generate or patch backend/.env.local ──────────────────────────────────

if [ "$NEEDS_NEW_ENV" = true ]; then
    # Create fresh .env.local
    if [ "$DB_BACKEND" = "postgres" ]; then
        cat > .env.local <<EOF
# ── Database Backend ──────────────────────────────────────────
DB_BACKEND=postgres
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/architecture_mcp

# ── Supabase (to switch: set DB_BACKEND=supabase and fill these in)
# SUPABASE_URL=https://your-project.supabase.co
# SUPABASE_KEY=your-supabase-anon-key

# ── AI (REQUIRED) ────────────────────────────────────────────
ANTHROPIC_API_KEY=

# ── Redis (optional — without it, analysis runs in-process) ──
REDIS_URL=redis://localhost:6379
EOF
    else
        cat > .env.local <<EOF
# ── Database Backend ──────────────────────────────────────────
DB_BACKEND=supabase
SUPABASE_URL=
SUPABASE_KEY=

# ── PostgreSQL (to switch: set DB_BACKEND=postgres and run docker compose up -d)
# DATABASE_URL=postgresql://postgres:postgres@localhost:5432/architecture_mcp

# ── AI (REQUIRED) ────────────────────────────────────────────
ANTHROPIC_API_KEY=

# ── Redis (optional — without it, analysis runs in-process) ──
REDIS_URL=redis://localhost:6379
EOF
    fi
    info "Created backend/.env.local (${DB_BACKEND} backend)"
fi

# Patch missing or empty required fields (works for both new and existing files)
echo ""
info "Checking backend/.env.local for missing values..."

if [ "$DB_BACKEND" = "postgres" ]; then
    env_ensure .env.local "DATABASE_URL" "DATABASE_URL: " "postgresql://postgres:postgres@localhost:5432/architecture_mcp"
elif [ "$DB_BACKEND" = "supabase" ]; then
    env_ensure .env.local "SUPABASE_URL" "SUPABASE_URL (from Supabase dashboard): "
    env_ensure .env.local "SUPABASE_KEY" "SUPABASE_KEY (from Supabase dashboard): "
fi

env_ensure .env.local "ANTHROPIC_API_KEY" "ANTHROPIC_API_KEY (from console.anthropic.com): "
env_ensure .env.local "REDIS_URL" "" "redis://localhost:6379"

cd ..

# ── Frontend ───────────────────────────────────────────────────────────────

info "Setting up frontend..."
cd frontend
npm install --silent
info "Frontend dependencies installed"

if [ ! -f ".env.local" ]; then
    cat > .env.local <<EOF
NEXT_PUBLIC_API_URL=http://localhost:8000
EOF
    info "Generated frontend/.env.local"
else
    info "frontend/.env.local already exists — checking..."
fi

# Patch frontend env if needed
env_ensure .env.local "NEXT_PUBLIC_API_URL" "" "http://localhost:8000"

cd ..

# ── Done ───────────────────────────────────────────────────────────────────

echo ""
info "Setup complete! Start everything with:"
echo ""
echo "  ./start-dev.sh"
echo ""
echo "Or start services individually:"
echo ""
echo "  # Backend"
echo "  cd backend && PYTHONPATH=src .venv/bin/uvicorn main:app --reload --port 8000"
echo ""
echo "  # Frontend"
echo "  cd frontend && npm run dev"
echo ""
echo "  # Worker (optional, requires Redis)"
echo "  cd backend && PYTHONPATH=src .venv/bin/arq workers.tasks.WorkerSettings"
echo ""
