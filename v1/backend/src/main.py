"""Application entry point."""
import uvicorn
from api.app import create_app
from config.settings import get_settings

app = create_app()

if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        reload_dirs=["src"] if settings.debug else None,
    )


