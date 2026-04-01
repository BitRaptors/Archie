"""MCP Streamable HTTP transport routes.

Mounts the MCP server over Streamable HTTP using the SDK's
StreamableHTTPSessionManager. A single ASGI endpoint handles
GET (SSE streams), POST (messages), and DELETE (cleanup).

Endpoint: /mcp/
"""
import logging

logger = logging.getLogger(__name__)

# Try to import MCP — graceful degradation if not installed.
try:
    from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
    from infrastructure.mcp.server import server as mcp_server
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    mcp_server = None

# Build the ASGI app.
_session_manager = None

if MCP_AVAILABLE:
    _session_manager = StreamableHTTPSessionManager(
        app=mcp_server,
        stateless=True,
    )

    async def mcp_app(scope, receive, send):
        """Raw ASGI app — delegates everything to the session manager."""
        logger.info("MCP client request: %s %s", scope.get("method", "?"), scope.get("path", "?"))
        await _session_manager.handle_request(scope, receive, send)
else:
    from starlette.responses import JSONResponse as StarletteJSONResponse

    async def mcp_app(scope, receive, send):
        response = StarletteJSONResponse(
            {"error": "MCP not installed. pip install mcp>=1.0.0"},
            status_code=503,
        )
        await response(scope, receive, send)


def get_session_manager():
    """Return the session manager instance (or None if MCP unavailable)."""
    return _session_manager
