#!/bin/bash

# Architecture MCP Server Startup Script

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Architecture MCP Server${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Check Python version
echo -e "${YELLOW}Checking Python version...${NC}"
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}✗ Python 3 is not installed${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
echo -e "${GREEN}✓ Python ${PYTHON_VERSION} found${NC}"

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv .venv
    echo -e "${GREEN}✓ Virtual environment created${NC}"
fi

# Activate virtual environment
echo -e "${YELLOW}Activating virtual environment...${NC}"
source .venv/bin/activate
echo -e "${GREEN}✓ Virtual environment activated${NC}"

# Check if requirements are installed
echo -e "${YELLOW}Checking dependencies...${NC}"
if ! python3 -c "import mcp" 2>/dev/null; then
    echo -e "${YELLOW}Installing dependencies...${NC}"
    pip install -q --upgrade pip
    pip install -q -r requirements.txt
    echo -e "${GREEN}✓ Dependencies installed${NC}"
else
    echo -e "${GREEN}✓ Dependencies already installed${NC}"
fi

# Check if DOCS directory exists
if [ ! -d "DOCS" ]; then
    echo -e "${RED}✗ DOCS directory not found${NC}"
    exit 1
fi

# Check if DOCS has content
if [ ! -d "DOCS/backend" ] || [ ! -d "DOCS/frontend" ]; then
    echo -e "${RED}✗ DOCS directory is missing backend or frontend documentation${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Documentation found${NC}"
echo ""

# Display server info
echo -e "${BLUE}Server Configuration:${NC}"
echo -e "  ${YELLOW}Working Directory:${NC} $SCRIPT_DIR"
echo -e "  ${YELLOW}Python:${NC} $(python3 --version)"
echo -e "  ${YELLOW}MCP Server:${NC} architecture-blueprints"
echo ""

# Print integration guide
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Cursor MCP Integration${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${YELLOW}Add this configuration to your Cursor MCP settings:${NC}"
echo ""

# Get absolute paths
SCRIPT_DIR_ABS=$(cd "$SCRIPT_DIR" && pwd)
PYTHON_PATH="$SCRIPT_DIR_ABS/.venv/bin/python3"
RUN_SERVER_PATH="$SCRIPT_DIR_ABS/run_server.py"

cat << EOF
{
  "mcpServers": {
    "architecture": {
      "command": "$PYTHON_PATH",
      "args": ["$RUN_SERVER_PATH"],
      "cwd": "$SCRIPT_DIR_ABS"
    }
  }
}
EOF

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Start the server
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  Starting MCP Server...${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Run the server (it will output "✓ MCP server is running..." to stderr when ready)
python3 -m src.server 2>&1

