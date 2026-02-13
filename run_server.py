#!/usr/bin/env python3
"""Entry point for the MCP server that ensures proper module resolution."""

import sys
from pathlib import Path

# Add the project root and backend/src to Python path
project_root = Path(__file__).parent.resolve()
backend_src = project_root / "backend" / "src"

for path in [str(project_root), str(backend_src)]:
    if path not in sys.path:
        sys.path.insert(0, path)

# Load .env.local from backend/ before importing anything that uses settings.
from dotenv import load_dotenv  # noqa: E402

_env_file = project_root / "backend" / ".env.local"
if _env_file.exists():
    load_dotenv(str(_env_file), override=False)
else:
    print(
        f"⚠ MCP server: backend/.env.local not found at {_env_file}. "
        "Database features (active repo filtering) will be unavailable.",
        file=sys.stderr,
    )

# Now import and run the server
if __name__ == "__main__":
    from infrastructure.mcp.server import main
    import asyncio
    asyncio.run(main())
