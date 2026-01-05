#!/usr/bin/env python3
"""Entry point for the MCP server that ensures proper module resolution."""

import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.resolve()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Now import and run the server
if __name__ == "__main__":
    from src.server import main
    import asyncio
    asyncio.run(main())

