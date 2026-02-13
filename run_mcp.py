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

# Load .env.local from backend/ BEFORE any module imports settings.
# settings.py uses load_dotenv(".env.local") relative to CWD, but
# the actual file lives in backend/.  Pre-loading it here ensures
# the env vars are available when get_settings() is first called.
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

if __name__ == "__main__":
    from infrastructure.mcp.server import main
    import asyncio

    asyncio.run(main())
