"""API v1 router."""
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1", tags=["v1"])

# Routes will be registered here
# from api.routes import auth, repositories, analyses
# router.include_router(auth.router)
# router.include_router(repositories.router)
# router.include_router(analyses.router)


