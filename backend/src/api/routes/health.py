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


@router.get("/system/pick-folder")
async def pick_folder():
    """Open a native folder selection dialog and return the path."""
    import subprocess
    import platform

    if platform.system() == "Darwin":
        try:
            # Use osascript to open the native Mac folder picker
            script = 'POSIX path of (choose folder with prompt "Select Project Folder")'
            result = subprocess.run(['osascript', '-e', script], capture_output=True, text=True)
            if result.returncode == 0:
                return {"path": result.stdout.strip()}
            else:
                return {"path": None, "error": "Operation cancelled or failed"}
        except Exception as e:
            return {"path": None, "error": str(e)}
    
    return {"path": None, "error": f"Folder picking not supported on {platform.system()}"}