"""Authentication routes."""
from fastapi import APIRouter, Depends, HTTPException
from api.dto.requests import GitHubAuthRequest
from application.services.github_service import GitHubService
from config.settings import get_settings

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/config")
async def get_auth_config():
    """Return whether a server-side GitHub token is configured.
    
    The frontend uses this to decide whether to prompt the user for a token
    or to skip authentication entirely.
    """
    settings = get_settings()
    has_token = bool(settings.github_token and settings.github_token.strip())
    return {"server_token_configured": has_token}


@router.post("/github")
async def authenticate_github(request: GitHubAuthRequest):
    """Validate and store a user-provided GitHub token."""
    github_service = GitHubService()
    
    # Validate token
    is_valid = await github_service.validate_token(request.token)
    if not is_valid:
        raise HTTPException(status_code=401, detail="Invalid GitHub token")
    
    return {"status": "authenticated"}


@router.get("/status")
async def get_auth_status():
    """Check authentication status."""
    return {"authenticated": False}


@router.delete("/")
async def logout():
    """Remove authentication."""
    return {"status": "logged_out"}


