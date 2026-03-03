"""MCP SSE transport routes.

Mounts the MCP server over SSE using the SDK's SseServerTransport.
Two ASGI endpoints:
  GET  /mcp/sse       — SSE stream (client connects here)
  POST /mcp/messages  — client sends JSON-RPC messages here
"""
import logging

from starlette.applications import Starlette
from starlette.routing import Route, Mount

logger = logging.getLogger(__name__)

# Try to import MCP — graceful degradation if not installed.
try:
    from mcp.server.sse import SseServerTransport
    from infrastructure.mcp.server import server as mcp_server
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    mcp_server = None

# The SSE transport directs clients to POST to this relative path.
# When the Starlette sub-app is mounted at /mcp, the full path becomes /mcp/messages.
_sse_transport = SseServerTransport("/messages") if MCP_AVAILABLE else None


async def handle_sse(scope, receive, send):
    """GET /mcp/sse — establish an SSE stream with the MCP client.

    This is a raw ASGI handler (not a Starlette endpoint) because
    SseServerTransport.connect_sse writes the response directly via
    the ASGI send callable. A Route endpoint would try to call the
    return value as a Response, causing TypeError on None.
    """
    logger.info("MCP SSE client connecting")
    async with _sse_transport.connect_sse(
        scope, receive, send
    ) as (read_stream, write_stream):
        await mcp_server.run(
            read_stream,
            write_stream,
            mcp_server.create_initialization_options(),
        )


# Build the Starlette sub-application.
# - /sse and /messages are both raw ASGI apps (they send responses directly)
if MCP_AVAILABLE and _sse_transport is not None:
    mcp_app = Starlette(
        routes=[
            Mount("/sse", app=handle_sse),
            Mount("/messages", app=_sse_transport.handle_post_message),
        ],
    )
else:
    from starlette.responses import JSONResponse as StarletteJSONResponse

    async def _unavailable(scope, receive, send):
        response = StarletteJSONResponse(
            {"error": "MCP not installed. pip install mcp>=1.0.0"},
            status_code=503,
        )
        await response(scope, receive, send)

    mcp_app = Starlette(
        routes=[
            Route("/sse", endpoint=lambda r: StarletteJSONResponse(
                {"error": "MCP not installed"}, status_code=503
            )),
            Mount("/messages", app=_unavailable),
        ],
    )
