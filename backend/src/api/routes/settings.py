"""Analysis settings routes — ignored directories and library capabilities."""
from fastapi import APIRouter, HTTPException, Request

from api.dto.requests import UpdateIgnoredDirsRequest, UpdateLibraryCapabilitiesRequest
from api.dto.responses import IgnoredDirectoryResponse, LibraryCapabilityResponse
from domain.entities.analysis_settings import (
    CAPABILITY_OPTIONS,
    DEFAULT_IGNORED_DIRS,
    DEFAULT_LIBRARY_CAPABILITIES,
    ECOSYSTEM_OPTIONS,
)
from infrastructure.persistence.analysis_settings_repository import (
    IgnoredDirsRepository,
    LibraryCapabilitiesRepository,
)

router = APIRouter(prefix="/settings", tags=["settings"])


async def _get_ignored_dirs_repo(request: Request) -> IgnoredDirsRepository:
    db = await request.app.container.db()
    return IgnoredDirsRepository(db=db)


async def _get_lib_caps_repo(request: Request) -> LibraryCapabilitiesRepository:
    db = await request.app.container.db()
    return LibraryCapabilitiesRepository(db=db)


# ── Ignored Directories ──────────────────────────────────────────

@router.get("/ignored-dirs", response_model=list[IgnoredDirectoryResponse])
async def list_ignored_dirs(request: Request):
    """List all discovery ignored directories."""
    repo = await _get_ignored_dirs_repo(request)
    dirs = await repo.get_all()
    return [IgnoredDirectoryResponse(**d.model_dump()) for d in dirs]


@router.put("/ignored-dirs", response_model=list[IgnoredDirectoryResponse])
async def update_ignored_dirs(body: UpdateIgnoredDirsRequest, request: Request):
    """Replace all ignored directories with the provided list."""
    repo = await _get_ignored_dirs_repo(request)
    dirs = await repo.replace_all(body.directories)
    return [IgnoredDirectoryResponse(**d.model_dump()) for d in dirs]


@router.post("/ignored-dirs/reset", response_model=list[IgnoredDirectoryResponse])
async def reset_ignored_dirs(request: Request):
    """Reset ignored directories to seed defaults."""
    repo = await _get_ignored_dirs_repo(request)
    dirs = await repo.replace_all(sorted(DEFAULT_IGNORED_DIRS))
    return [IgnoredDirectoryResponse(**d.model_dump()) for d in dirs]


# ── Library Capabilities ─────────────────────────────────────────

@router.get("/ecosystem-options", response_model=list[str])
async def get_ecosystem_options():
    """Return the predefined list of valid ecosystem values."""
    return ECOSYSTEM_OPTIONS


@router.get("/capability-options", response_model=list[str])
async def get_capability_options():
    """Return the predefined list of valid capability values."""
    return CAPABILITY_OPTIONS


@router.get("/library-capabilities", response_model=list[LibraryCapabilityResponse])
async def list_library_capabilities(request: Request):
    """List all library capability mappings."""
    repo = await _get_lib_caps_repo(request)
    libs = await repo.get_all()
    return [LibraryCapabilityResponse(**lib.model_dump()) for lib in libs]


@router.put("/library-capabilities", response_model=list[LibraryCapabilityResponse])
async def update_library_capabilities(body: UpdateLibraryCapabilitiesRequest, request: Request):
    """Replace all library capabilities with the provided list."""
    valid = set(CAPABILITY_OPTIONS)
    for lib in body.libraries:
        invalid = [c for c in lib.capabilities if c not in valid]
        if invalid:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid capabilities for '{lib.library_name}': {invalid}. "
                       f"Valid options: {CAPABILITY_OPTIONS}",
            )
    repo = await _get_lib_caps_repo(request)
    libs = await repo.replace_all([lib.model_dump() for lib in body.libraries])
    return [LibraryCapabilityResponse(**lib.model_dump()) for lib in libs]


@router.post("/library-capabilities/reset", response_model=list[LibraryCapabilityResponse])
async def reset_library_capabilities(request: Request):
    """Reset library capabilities to seed defaults."""
    repo = await _get_lib_caps_repo(request)
    rows = [
        {"library_name": name, "ecosystem": info["ecosystem"], "capabilities": info["capabilities"]}
        for name, info in sorted(DEFAULT_LIBRARY_CAPABILITIES.items())
    ]
    libs = await repo.replace_all(rows)
    return [LibraryCapabilityResponse(**lib.model_dump()) for lib in libs]
