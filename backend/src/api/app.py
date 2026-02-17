"""FastAPI application factory."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from config.container import Container
from config.settings import get_settings
from domain.exceptions.domain_exceptions import DomainException
from api.middleware.error_handler import domain_exception_handler
from application.services.analysis_data_collector import analysis_data_collector


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan for initializing resources."""
    # Initialize container resources
    await app.container.init_resources()

    # Initialize analysis_data_collector with DB client for cross-process persistence
    db = await app.container.db()
    analysis_data_collector.initialize(db)

    yield
    # Shutdown resources
    await app.container.shutdown_resources()


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    settings = get_settings()
    container = Container()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Store container in app state
    app.container = container

    # Exception handlers
    @app.exception_handler(Exception)
    async def global_exception_handler(request, exc):
        import traceback
        print(f"GLOBAL ERROR: {str(exc)}")
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"detail": str(exc), "traceback": traceback.format_exc()}
        )

    app.add_exception_handler(DomainException, domain_exception_handler)

    # Register routes
    from api.routes import auth, repositories, analyses, prompts, health, workspace, delivery
    from api.routes.mcp import mcp_app

    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(repositories.router, prefix="/api/v1")
    app.include_router(analyses.router, prefix="/api/v1")
    app.include_router(prompts.router, prefix="/api/v1")
    app.include_router(health.router, prefix="/api/v1")
    app.include_router(workspace.router, prefix="/api/v1")
    app.include_router(delivery.router, prefix="/api/v1")

    # Mount MCP SSE as a Starlette sub-app (raw ASGI, not FastAPI router)
    app.mount("/mcp", mcp_app)

    @app.get("/health")
    async def health():
        """Health check endpoint."""
        return {"status": "ok", "version": settings.app_version}

    return app
