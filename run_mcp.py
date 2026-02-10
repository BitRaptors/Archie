#!/usr/bin/env python3
"""Entry point for the MCP server (Cursor integration).

Ensures backend/src is on sys.path so all internal imports
(domain.*, infrastructure.*, etc.) resolve correctly.
"""

import os
import sys
from pathlib import Path

# Project root and backend source
project_root = Path(__file__).parent.absolute()
backend_src = project_root / "backend" / "src"

# Add backend/src to sys.path so bare imports like
# `from domain.entities.blueprint import ...` work.
for p in [str(project_root), str(backend_src)]:
    if p not in sys.path:
        sys.path.insert(0, p)

os.chdir(str(project_root))

if __name__ == "__main__":
    from infrastructure.mcp.server import main
    import asyncio

    asyncio.run(main())
