"""Health check routes."""
from fastapi import APIRouter
from pathlib import Path

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}


@router.get("/system/path")
async def get_project_path():
    """Get the absolute path to the project root."""
    # backend/src/api/routes/health.py -> go up 4 levels to get to project root
    project_root = Path(__file__).parent.parent.parent.parent.parent.absolute()
    return {"path": str(project_root)}


