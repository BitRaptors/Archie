#!/usr/bin/env python3
"""
Startup script for Archie
Starts both backend and frontend servers
"""

import subprocess
import sys
import signal
import os
import time
from pathlib import Path

# Colors for output
GREEN = '\033[0;32m'
BLUE = '\033[0;34m'
YELLOW = '\033[1;33m'
RED = '\033[0;31m'
NC = '\033[0m'  # No Color

backend_process = None
frontend_process = None


def cleanup(signum, frame):
    """Cleanup function to stop both servers"""
    print(f"\n{YELLOW}🛑 Shutting down servers...{NC}")
    if backend_process:
        backend_process.terminate()
    if frontend_process:
        frontend_process.terminate()
    sys.exit(0)


def check_env_files():
    """Check if required .env.local files exist"""
    backend_env = Path("backend/.env.local")
    frontend_env = Path("frontend/.env.local")
    
    if not backend_env.exists():
        print(f"{RED}❌ Error: backend/.env.local not found{NC}")
        print("Please create it from backend/.env.example")
        sys.exit(1)
    
    if not frontend_env.exists():
        print(f"{RED}❌ Error: frontend/.env.local not found{NC}")
        print("Please create it from frontend/.env.example")
        sys.exit(1)


def _parse_redis_url() -> tuple[str, str, int]:
    """Read REDIS_URL from backend/.env.local and parse host/port."""
    redis_url = "redis://localhost:6379"
    env_file = Path("backend/.env.local")
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line.startswith("REDIS_URL=") and not line.startswith("#"):
                val = line.split("=", 1)[1].strip().strip('"').strip("'")
                if val:
                    redis_url = val
                break
    # Parse redis://host:port
    import re
    m = re.match(r'^redis://([^:/]+)(?::(\d+))?', redis_url)
    host = m.group(1) if m else "localhost"
    port = int(m.group(2)) if m and m.group(2) else 6379
    return redis_url, host, port


REDIS_URL, REDIS_HOST, REDIS_PORT = _parse_redis_url()


def check_redis():
    """Check if Redis is reachable."""
    import socket
    try:
        s = socket.create_connection((REDIS_HOST, REDIS_PORT), timeout=1)
        s.close()
        return True
    except (ConnectionRefusedError, OSError):
        return False


def start_backend():
    """Start the backend server and optionally the ARQ worker."""
    global backend_process

    print(f"{BLUE}📦 Starting backend server...{NC}")

    backend_dir = Path("backend")
    venv_python = backend_dir / ".venv" / "bin" / "python"

    # Check if virtual environment exists
    if not venv_python.exists():
        print(f"{YELLOW}⚠️  Virtual environment not found. Creating...{NC}")
        subprocess.run(["python3", "-m", "venv", ".venv"], cwd=backend_dir, check=True)
        subprocess.run([str(venv_python), "-m", "pip", "install", "--upgrade", "pip"], check=True)
        subprocess.run([str(venv_python), "-m", "pip", "install", "-r", "requirements.txt"], cwd=backend_dir, check=True)

    # Read backend port from .env.local (PORT key, default 8000)
    import json as _json
    backend_port = 8000
    env_local = backend_dir / ".env.local"
    if env_local.exists():
        import re as _re
        for line in env_local.read_text().splitlines():
            m = _re.match(r'^PORT\s*=\s*(\d+)', line)
            if m:
                backend_port = int(m.group(1))
                break

    # Check if prompts/schema version is stale
    prompts_file = backend_dir / "prompts.json"
    version_file = backend_dir / ".prompts-version"
    try:
        current = str(_json.loads(prompts_file.read_text())["version"])
        synced = version_file.read_text().strip() if version_file.exists() else ""
        if current != synced:
            print(f"{RED}⚠️  Updates available (v{synced or 'old'} → v{current}). Run: ./setup.sh{NC}")
            print(f"{RED}Cannot start — database schema or prompts are incompatible. Run ./setup.sh first.{NC}")
            sys.exit(1)
    except Exception:
        pass

    # Start backend
    backend_process = subprocess.Popen(
        [str(venv_python), "src/main.py"],
        cwd=backend_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Start ARQ worker only if Redis is available
    worker_process = None
    if check_redis():
        print(f"{BLUE}👷 Starting ARQ worker...{NC}")
        env = os.environ.copy()
        env["PYTHONPATH"] = str(backend_dir / "src") + os.pathsep + env.get("PYTHONPATH", "")
        worker_process = subprocess.Popen(
            [str(venv_python), "-m", "arq", "workers.tasks.WorkerSettings"],
            cwd=backend_dir,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    else:
        print(f"{YELLOW}ℹ️  Redis not available ({REDIS_URL}) — analysis will run in-process{NC}")

    # Wait a moment and check if it started
    time.sleep(2)
    if backend_process.poll() is not None:
        print(f"{RED}❌ Backend failed to start{NC}")
        stdout, stderr = backend_process.communicate()
        print(stderr.decode())
        sys.exit(1)

    print(f"{GREEN}✅ Backend running on http://localhost:{backend_port} (PID: {backend_process.pid}){NC}")
    if worker_process and worker_process.poll() is None:
        print(f"{GREEN}✅ Worker running (PID: {worker_process.pid}){NC}")
    print()
    return backend_process, backend_port


def start_frontend():
    """Start the frontend server"""
    global frontend_process
    
    print(f"{BLUE}📦 Starting frontend server...{NC}")
    
    frontend_dir = Path("frontend")
    node_modules = frontend_dir / "node_modules"
    
    # Check if node_modules exists
    if not node_modules.exists():
        print(f"{YELLOW}⚠️  Node modules not found. Installing...{NC}")
        subprocess.run(["npm", "install"], cwd=frontend_dir, check=True)
    
    # Create a temporary log file to capture output
    import tempfile
    log_file = tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.log')
    log_file.close()
    
    # Start frontend and capture output
    frontend_process = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=frontend_dir,
        stdout=open(log_file.name, 'w'),
        stderr=subprocess.STDOUT,
        text=True,
    )
    
    # Wait for Next.js to start and extract the port
    frontend_port = 4000
    import re
    
    for i in range(15):
        time.sleep(1)
        # Check if process is still running
        if frontend_process.poll() is not None:
            print(f"{RED}❌ Frontend failed to start{NC}")
            with open(log_file.name, 'r') as f:
                print(f.read())
            os.unlink(log_file.name)
            if backend_process:
                backend_process.terminate()
            sys.exit(1)
        
        # Read the log file to find the port
        try:
            with open(log_file.name, 'r') as f:
                content = f.read()
                # Look for port in output (e.g., "Local: http://localhost:3002")
                port_match = re.search(r'Local:\s+http://localhost:(\d+)', content)
                if port_match:
                    frontend_port = int(port_match.group(1))
                    break
                # Also try simpler pattern
                port_match = re.search(r'localhost:(\d+)', content)
                if port_match:
                    frontend_port = int(port_match.group(1))
                    # Only use if it's a reasonable port (3000-3010)
                    if 3000 <= frontend_port <= 5000:
                        break
        except Exception:
            pass
    
    # Clean up log file
    try:
        os.unlink(log_file.name)
    except Exception:
        pass
    
    # Final check if it started
    if frontend_process.poll() is not None:
        print(f"{RED}❌ Frontend failed to start{NC}")
        if backend_process:
            backend_process.terminate()
        sys.exit(1)
    
    print(f"{GREEN}✅ Frontend running on http://localhost:{frontend_port} (PID: {frontend_process.pid}){NC}\n")
    return frontend_process, frontend_port


def main():
    """Main function"""
    # Register signal handlers
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)
    
    print(f"{BLUE}🚀 Starting Archie...{NC}\n")
    
    # Check environment files
    check_env_files()
    
    # Start backend
    _, backend_port = start_backend()

    # Start frontend and get the actual port
    frontend_process, frontend_port = start_frontend()

    # Print status
    print(f"{GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{NC}")
    print(f"{GREEN}✨ Archie is running!{NC}")
    print(f"{GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{NC}")
    redis_status = REDIS_URL if check_redis() else f"Not connected ({REDIS_URL})"
    print(f"{BLUE}Backend:{NC}  http://localhost:{backend_port}")
    print(f"{BLUE}Frontend:{NC} http://localhost:{frontend_port}")
    print(f"{BLUE}API Docs:{NC} http://localhost:{backend_port}/docs")
    print(f"{BLUE}Redis:{NC}    {redis_status}")
    print(f"{GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{NC}")
    print(f"{YELLOW}Press Ctrl+C to stop both servers{NC}\n")
    
    # Wait for processes
    try:
        backend_process.wait()
        frontend_process.wait()
    except KeyboardInterrupt:
        cleanup(None, None)


if __name__ == "__main__":
    main()

