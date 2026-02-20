"""Analysis settings routes — ignored directories and library capabilities."""
import logging
import re
import shutil
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

logger = logging.getLogger(__name__)

from api.dto.requests import UpdateIgnoredDirsRequest, UpdateLibraryCapabilitiesRequest
from api.dto.responses import IgnoredDirectoryResponse, LibraryCapabilityResponse
from domain.entities.analysis_settings import (
    CAPABILITY_OPTIONS,
    ECOSYSTEM_OPTIONS,
    SEED_IGNORED_DIRS,
    SEED_LIBRARY_CAPABILITIES,
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
    dirs = await repo.replace_all(sorted(SEED_IGNORED_DIRS))
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
        for name, info in sorted(SEED_LIBRARY_CAPABILITIES.items())
    ]
    libs = await repo.replace_all(rows)
    return [LibraryCapabilityResponse(**lib.model_dump()) for lib in libs]


# ── Reset All Data ──────────────────────────────────────────────

def _parse_reset_tables() -> list[str]:
    """Derive user-data tables from the migration SQL files.

    1. Parses ``CREATE TABLE`` statements from the initial migration.
    2. Scans **all** ``.sql`` files in the migrations directory for
       ``INSERT INTO`` to find seeded tables.
    3. Builds FK parent→child relationships so that tables whose
       *only* FK parents are seeded are also excluded (e.g.
       ``prompt_revisions`` only references ``analysis_prompts``).
    4. Returns tables in reverse-creation order (children before
       parents) so deletes respect foreign-key constraints.
    """
    migrations_dir = Path(__file__).resolve().parents[3] / "migrations"
    schema_sql = (migrations_dir / "001_initial_setup.sql").read_text()

    # All tables in creation order
    all_tables = re.findall(r"CREATE TABLE IF NOT EXISTS\s+(\w+)", schema_sql)

    # Seeded tables from ALL .sql files in the migrations directory
    seeded: set[str] = set()
    for sql_file in migrations_dir.glob("*.sql"):
        seeded.update(re.findall(r"INSERT INTO\s+(\w+)", sql_file.read_text()))

    # FK relationships: child table → set of parent tables
    # Matches:  REFERENCES parent_table(id) ON DELETE CASCADE
    fk_parents: dict[str, set[str]] = {}
    current_table = None
    for line in schema_sql.splitlines():
        m = re.match(r"CREATE TABLE IF NOT EXISTS\s+(\w+)", line)
        if m:
            current_table = m.group(1)
        if current_table:
            for parent in re.findall(r"REFERENCES\s+(\w+)\(", line):
                fk_parents.setdefault(current_table, set()).add(parent)

    # Propagate: also exclude FK children of seeded tables
    # (e.g. prompt_revisions only exists to serve analysis_prompts)
    excluded = set(seeded)
    changed = True
    while changed:
        changed = False
        for table in all_tables:
            if table in excluded:
                continue
            parents = fk_parents.get(table, set())
            if parents & excluded:
                excluded.add(table)
                changed = True

    all_tables.reverse()  # reverse creation order = safe deletion order
    return [t for t in all_tables if t not in excluded]


_RESET_TABLES = _parse_reset_tables()


@router.post("/reset-data")
async def reset_all_data(request: Request):
    """Wipe all user data, re-seed settings, and clear local storage."""
    db = await request.app.container.db()
    storage = request.app.container.storage()
    errors: list[str] = []

    # 1. Delete from user-data tables in dependency order
    for table_name in _RESET_TABLES:
        try:
            result = await db.table(table_name).delete().neq(
                "id", "00000000-0000-0000-0000-000000000000"
            ).execute()
            deleted_count = len(result.data) if result.data else 0
            logger.info("reset-data: cleared %s (%d rows)", table_name, deleted_count)
        except Exception as exc:
            msg = f"Failed to clear {table_name}: {exc}"
            logger.error("reset-data: %s", msg, exc_info=True)
            errors.append(msg)

    # 2. Re-seed discovery_ignored_dirs
    try:
        dirs_repo = await _get_ignored_dirs_repo(request)
        await dirs_repo.replace_all(sorted(SEED_IGNORED_DIRS))
        logger.info("reset-data: re-seeded ignored dirs")
    except Exception as exc:
        msg = f"Failed to re-seed ignored dirs: {exc}"
        logger.error("reset-data: %s", msg, exc_info=True)
        errors.append(msg)

    # 3. Re-seed library_capabilities
    try:
        libs_repo = await _get_lib_caps_repo(request)
        rows = [
            {"library_name": name, "ecosystem": info["ecosystem"], "capabilities": info["capabilities"]}
            for name, info in sorted(SEED_LIBRARY_CAPABILITIES.items())
        ]
        await libs_repo.replace_all(rows)
        logger.info("reset-data: re-seeded library capabilities")
    except Exception as exc:
        msg = f"Failed to re-seed library capabilities: {exc}"
        logger.error("reset-data: %s", msg, exc_info=True)
        errors.append(msg)

    # 4. Wipe and recreate storage directories
    base = Path(storage._base_path)
    for dir_name in ("blueprints", "repos"):
        target = base / dir_name
        try:
            if target.exists():
                shutil.rmtree(target)
            target.mkdir(parents=True, exist_ok=True)
            logger.info("reset-data: wiped %s/", dir_name)
        except Exception as exc:
            msg = f"Failed to wipe {dir_name}/: {exc}"
            logger.error("reset-data: %s", msg, exc_info=True)
            errors.append(msg)

    if errors:
        raise HTTPException(status_code=500, detail={
            "message": "Reset completed with errors",
            "errors": errors,
        })

    return {"reset": True}
