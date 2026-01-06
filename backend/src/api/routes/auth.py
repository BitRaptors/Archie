"""Authentication routes."""
from fastapi import APIRouter, Depends, HTTPException
from api.dto.requests import GitHubAuthRequest
from application.services.github_service import GitHubService
from cryptography.fernet import Fernet
from config.settings import get_settings

router = APIRouter(prefix="/auth", tags=["auth"])


def get_encryption_key() -> bytes:
    """Get encryption key for tokens."""
    settings = get_settings()
    # In production, use a proper key from secrets
    key = settings.supabase_jwt_secret.encode()[:32].ljust(32, b'0')
    return Fernet.generate_key()  # Simplified - should use proper key management


@router.post("/github")
async def authenticate_github(request: GitHubAuthRequest):
    """Store GitHub token."""
    github_service = GitHubService()
    
    # Validate token
    is_valid = await github_service.validate_token(request.token)
    if not is_valid:
        raise HTTPException(status_code=401, detail="Invalid GitHub token")
    
    # Encrypt token
    key = get_encryption_key()
    fernet = Fernet(key)
    encrypted_token = fernet.encrypt(request.token.encode())
    
    # Store in database (would use user repository)
    # For now, return success
    return {"status": "authenticated"}


@router.get("/status")
async def get_auth_status():
    """Check authentication status."""
    # Would check if user is authenticated
    return {"authenticated": False}


@router.delete("/")
async def logout():
    """Remove authentication."""
    return {"status": "logged_out"}


