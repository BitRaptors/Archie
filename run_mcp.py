import os
import sys
from pathlib import Path

# Add the current directory to sys.path so we can import from src
current_dir = Path(__file__).parent.absolute()
sys.path.append(str(current_dir))

if __name__ == "__main__":
    from backend.src.infrastructure.mcp.server import server
    from mcp.server.stdio import stdio_server
    import asyncio
    
    # Ensure we're in the right directory
    os.chdir(str(current_dir))
    
    async def run_stdio():
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options()
            )

    try:
        asyncio.run(run_stdio())
    except KeyboardInterrupt:
        pass

