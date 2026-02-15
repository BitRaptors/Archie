"""MCP SSE transport routes.

Mounts the MCP server over SSE using the SDK's SseServerTransport.
Two ASGI endpoints:
  GET  /mcp/sse       — SSE stream (client connects here)
  POST /mcp/messages  — client sends JSON-RPC messages here
"""
import logging

from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.requests import Request

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


async def handle_sse(request: Request):
    """GET /mcp/sse — establish an SSE stream with the MCP client."""
    logger.info("MCP SSE client connecting")
    async with _sse_transport.connect_sse(
        request.scope, request.receive, request._send
    ) as (read_stream, write_stream):
        await mcp_server.run(
            read_stream,
            write_stream,
            mcp_server.create_initialization_options(),
        )


# Build the Starlette sub-application.
# - /sse uses a normal endpoint (connect_sse is a blocking context manager → works fine)
# - /messages mounts handle_post_message directly as an ASGI app
#   (it sends its own response via raw ASGI send, so it can't be a Route endpoint)
if MCP_AVAILABLE and _sse_transport is not None:
    mcp_app = Starlette(
        routes=[
            Route("/sse", endpoint=handle_sse),
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
