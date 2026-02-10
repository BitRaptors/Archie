"""MCP server for architecture blueprints.

This is a thin wrapper that delegates to the backend infrastructure MCP server.
"""

import sys
from pathlib import Path

# Add backend/src to path so we can import from infrastructure.mcp
backend_src = Path(__file__).parent.parent / "backend" / "src"
if str(backend_src) not in sys.path:
    sys.path.insert(0, str(backend_src))

# Re-export from the backend MCP server
from infrastructure.mcp.server import server, main, create_server

__all__ = ["server", "main", "create_server"]

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
