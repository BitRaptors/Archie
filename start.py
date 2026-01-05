#!/usr/bin/env python3
"""Unified startup script for Architecture MCP Server."""

import sys
import subprocess
import os
from pathlib import Path
from typing import Optional


def print_colored(text: str, color: str = "white") -> None:
    """Print colored text."""
    colors = {
        "red": "\033[0;31m",
        "green": "\033[0;32m",
        "yellow": "\033[1;33m",
        "blue": "\033[0;34m",
        "white": "\033[0m",
    }
    reset = "\033[0m"
    print(f"{colors.get(color, '')}{text}{reset}")


def check_python_version() -> bool:
    """Check if Python version is 3.8+."""
    if sys.version_info < (3, 8):
        print_colored("✗ Python 3.8+ is required", "red")
        print_colored(f"  Current version: {sys.version}", "red")
        return False
    print_colored(f"✓ Python {sys.version.split()[0]} found", "green")
    return True


def check_venv() -> Path:
    """Check if virtual environment exists, create if not."""
    script_dir = Path(__file__).parent.resolve()
    venv_dir = script_dir / ".venv"
    
    if not venv_dir.exists():
        print_colored("Creating virtual environment...", "yellow")
        subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
        print_colored("✓ Virtual environment created", "green")
    else:
        print_colored("✓ Virtual environment found", "green")
    
    return venv_dir.resolve()


def get_venv_python(venv_dir: Path) -> Path:
    """Get Python executable from virtual environment."""
    if sys.platform == "win32":
        python_exe = venv_dir / "Scripts" / "python.exe"
    else:
        python_exe = venv_dir / "bin" / "python"
    
    # Return absolute path - even if it's a symlink, the venv will handle it correctly
    # The key is that we use this path, not the resolved system Python
    abs_path = python_exe.absolute()
    
    # Verify the path exists
    if not abs_path.exists():
        raise FileNotFoundError(f"Virtual environment Python not found: {abs_path}")
    
    return abs_path


def install_dependencies(venv_python: Path) -> bool:
    """Install dependencies if needed."""
    venv_python_str = str(venv_python)
    
    # Verify we're using the venv Python (not system Python)
    if not venv_python.exists():
        print_colored(f"✗ Virtual environment Python not found: {venv_python_str}", "red")
        return False
    
    # Verify we're in a venv by checking sys.prefix
    try:
        result = subprocess.run(
            [venv_python_str, "-c", "import sys; print(sys.prefix)"],
            capture_output=True,
            text=True,
            check=True
        )
        venv_prefix = result.stdout.strip()
        script_dir = Path(__file__).parent.resolve()
        venv_dir = script_dir / ".venv"
        
        # Check if the prefix matches our venv directory
        if str(venv_dir) not in venv_prefix and str(venv_dir.resolve()) not in venv_prefix:
            print_colored(f"✗ Python is not using the virtual environment", "red")
            print_colored(f"  Expected venv: {venv_dir}", "red")
            print_colored(f"  Python prefix: {venv_prefix}", "red")
            return False
    except Exception as e:
        print_colored(f"Warning: Could not verify venv: {e}", "yellow")
    
    try:
        # Check if mcp is installed in venv
        result = subprocess.run(
            [venv_python_str, "-c", "import mcp"],
            capture_output=True,
            text=True,
            check=False
        )
        if result.returncode == 0:
            print_colored("✓ Dependencies already installed", "green")
            return True
    except Exception as e:
        print_colored(f"Warning: Could not check for mcp: {e}", "yellow")
    
    print_colored("Installing dependencies...", "yellow")
    try:
        # Upgrade pip first (use venv Python explicitly)
        # Use --isolated to avoid system-wide configuration interference
        subprocess.run(
            [venv_python_str, "-m", "pip", "install", "--isolated", "--upgrade", "pip", "-q"],
            check=True,
            capture_output=True
        )
        # Install requirements
        requirements = Path(__file__).parent / "requirements.txt"
        subprocess.run(
            [venv_python_str, "-m", "pip", "install", "--isolated", "-q", "-r", str(requirements)],
            check=True,
            capture_output=True
        )
        print_colored("✓ Dependencies installed", "green")
        return True
    except subprocess.CalledProcessError as e:
        error_output = ""
        if e.stderr:
            error_output = e.stderr.decode() if isinstance(e.stderr, bytes) else str(e.stderr)
        elif e.stdout:
            error_output = e.stdout.decode() if isinstance(e.stdout, bytes) else str(e.stdout)
        
        print_colored(f"✗ Failed to install dependencies", "red")
        if error_output:
            # Show first few lines of error
            error_lines = error_output.split('\n')[:5]
            for line in error_lines:
                if line.strip():
                    print_colored(f"  {line[:100]}", "red")
        return False


def check_docs() -> bool:
    """Check if documentation exists."""
    script_dir = Path(__file__).parent
    docs_dir = script_dir / "DOCS"
    
    if not docs_dir.exists():
        print_colored("✗ DOCS directory not found", "red")
        return False
    
    backend_dir = docs_dir / "backend"
    frontend_dir = docs_dir / "frontend"
    
    if not backend_dir.exists() or not frontend_dir.exists():
        print_colored("✗ DOCS directory is missing backend or frontend documentation", "red")
        return False
    
    print_colored("✓ Documentation found", "green")
    return True


def print_integration_guide(script_dir: Path, venv_python: Path) -> None:
    """Print Cursor MCP integration guide."""
    print_colored("", "white")
    print_colored("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", "blue")
    print_colored("  Cursor MCP Integration", "blue")
    print_colored("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", "blue")
    print_colored("", "white")
    print_colored("Add this configuration to your Cursor MCP settings:", "yellow")
    print_colored("", "white")
    
    # Use venv Python path directly (absolute but not resolved to avoid following symlinks)
    # This ensures we use the venv Python, not the system Python it points to
    python_path = str(venv_python.absolute())
    script_dir_path = str(script_dir.resolve())
    
    # Escape backslashes for Windows paths in JSON
    python_path_escaped = python_path.replace("\\", "\\\\")
    script_dir_path_escaped = script_dir_path.replace("\\", "\\\\")
    
    # Use absolute path for run_server.py to avoid cwd issues
    run_server_path = str((script_dir / "run_server.py").resolve())
    run_server_path_escaped = run_server_path.replace("\\", "\\\\")
    
    config_json = f'''{{
  "mcpServers": {{
    "architecture": {{
      "command": "{python_path_escaped}",
      "args": ["{run_server_path_escaped}"],
      "cwd": "{script_dir_path_escaped}"
    }}
  }}
}}'''
    
    print_colored(config_json, "green")
    print_colored("", "white")
    print_colored("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", "blue")
    print_colored("", "white")


def start_server(venv_python: Path) -> None:
    """Start the MCP server."""
    script_dir = Path(__file__).parent
    
    print_colored("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", "green")
    print_colored("  Starting MCP Server...", "green")
    print_colored("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", "green")
    print()
    
    # Change to script directory
    os.chdir(script_dir)
    
    # Start server (server will print "✓ MCP server is running..." to stderr when ready)
    try:
        subprocess.run(
            [str(venv_python), "-m", "src.server"],
            check=True
        )
    except KeyboardInterrupt:
        print_colored("\n\n✓ Server stopped by user", "yellow")
    except subprocess.CalledProcessError as e:
        print_colored(f"\n✗ Server error: {e}", "red")
        sys.exit(1)


def main() -> None:
    """Main startup function."""
    script_dir = Path(__file__).parent
    
    print_colored("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", "blue")
    print_colored("  Architecture MCP Server", "blue")
    print_colored("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", "blue")
    print()
    
    # Check Python version
    print_colored("Checking Python version...", "yellow")
    if not check_python_version():
        sys.exit(1)
    
    # Check/create virtual environment
    print_colored("Checking virtual environment...", "yellow")
    venv_dir = check_venv()
    venv_python = get_venv_python(venv_dir)
    
    # Install dependencies
    print_colored("Checking dependencies...", "yellow")
    if not install_dependencies(venv_python):
        sys.exit(1)
    
    # Check documentation
    print_colored("Checking documentation...", "yellow")
    if not check_docs():
        sys.exit(1)
    
    print()
    print_colored("Server Configuration:", "blue")
    print_colored(f"  Working Directory: {script_dir}", "yellow")
    print_colored(f"  Python: {sys.version.split()[0]}", "yellow")
    print_colored("  MCP Server: architecture-blueprints", "yellow")
    print()
    
    # Print integration guide
    print_integration_guide(script_dir, venv_python)
    
    # Start server
    start_server(venv_python)


if __name__ == "__main__":
    main()

