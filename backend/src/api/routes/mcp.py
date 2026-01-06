from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse

router = APIRouter()

# Try to import MCP - if not available, endpoints will return helpful errors
try:
    from infrastructure.mcp.server import server
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    server = None

@router.get("/mcp/sse")
async def sse_endpoint(request: Request):
    """MCP SSE endpoint for network connections."""
    if not MCP_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="MCP package not installed. Please install it with: pip install mcp>=1.0.0"
        )
    
    # For now, return a message that SSE transport is being implemented
    # The actual SSE implementation will be added once we verify the correct MCP API
    return JSONResponse(
        status_code=501,
        content={
            "message": "SSE transport is being implemented",
            "note": "For now, use the local stdio transport via run_mcp.py"
        }
    )

@router.post("/mcp/messages")
async def messages_endpoint(request: Request):
    """MCP messages endpoint for network connections."""
    if not MCP_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="MCP package not installed. Please install it with: pip install mcp>=1.0.0"
        )
    
    return JSONResponse(
        status_code=501,
        content={
            "message": "SSE transport is being implemented",
            "note": "For now, use the local stdio transport via run_mcp.py"
        }
    )

