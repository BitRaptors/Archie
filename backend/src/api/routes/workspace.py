"""Workspace routes -- manage analyzed repositories, active repo, agent files."""
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Request

from domain.entities.blueprint import StructuredBlueprint
from infrastructure.persistence.user_profile_repository import UserProfileRepository
from infrastructure.persistence.repository_repository import RepositoryRepository
from infrastructure.persistence.analysis_repository import AnalysisRepository
from application.services.agent_file_generator import generate_all

router = APIRouter(prefix="/workspace", tags=["workspace"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_repos(request: Request):
    """Get a RepositoryRepository from the container."""
    db = await request.app.container.db()
    return RepositoryRepository(db=db)


async def _get_profile_repo(request: Request):
    """Get a UserProfileRepository from the container."""
    db = await request.app.container.db()
    return UserProfileRepository(db=db)


async def _get_analysis_repo(request: Request):
    """Get an AnalysisRepository from the container."""
    db = await request.app.container.db()
    return AnalysisRepository(db=db)


def _get_storage(request: Request):
    """Get the storage instance from the container."""
    return request.app.container.storage()


# ---------------------------------------------------------------------------
# Repository listing
# ---------------------------------------------------------------------------

@router.get("/repositories")
async def list_repositories(request: Request):
    """List all analyzed repositories with metadata.

    Returns enriched list: name, language, date, whether structured
    blueprint exists, and storage size.
    """
    storage = _get_storage(request)
    repo_repo = await _get_repos(request)
    analysis_repo = await _get_analysis_repo(request)

    blueprints_dir = Path(storage._base_path) / "blueprints"
    if not blueprints_dir.exists():
        return []

    results = []
    for repo_dir in sorted(blueprints_dir.iterdir()):
        if not repo_dir.is_dir():
            continue

        repo_id = repo_dir.name
        has_json = (repo_dir / "blueprint.json").exists()
        if not has_json:
            continue

        # Basic entry
        entry = {
            "repo_id": repo_id,
            "name": repo_id,
            "language": None,
            "analyzed_at": None,
            "has_structured": True,
        }

        # Try to enrich from DB
        try:
            repo = await repo_repo.get_by_id(repo_id)
            if repo:
                entry["name"] = repo.full_name or f"{repo.owner}/{repo.name}"
                entry["language"] = repo.language
        except Exception:
            pass

        # Try to get display name from blueprint.json
        if has_json and entry["name"] == repo_id:
            try:
                data = json.loads((repo_dir / "blueprint.json").read_text(encoding="utf-8"))
                meta_name = (data.get("meta") or {}).get("repository", "")
                if meta_name:
                    entry["name"] = meta_name
            except Exception:
                pass

        # Get latest analysis date
        try:
            all_analyses = await analysis_repo.get_all(limit=500)
            repo_analyses = [a for a in all_analyses if a.repository_id == repo_id]
            if repo_analyses:
                latest = max(repo_analyses, key=lambda a: a.created_at)
                entry["analyzed_at"] = latest.created_at.isoformat()
        except Exception:
            pass

        results.append(entry)

    return results


# ---------------------------------------------------------------------------
# Active repository
# ---------------------------------------------------------------------------

@router.get("/active")
async def get_active(request: Request):
    """Get the currently active repository."""
    profile_repo = await _get_profile_repo(request)
    profile = await profile_repo.get_default()
    if not profile or not profile.active_repo_id:
        return {"active_repo_id": None, "repository": None}

    repo_repo = await _get_repos(request)
    repo = await repo_repo.get_by_id(profile.active_repo_id)

    return {
        "active_repo_id": profile.active_repo_id,
        "repository": {
            "id": repo.id,
            "name": repo.full_name or f"{repo.owner}/{repo.name}",
            "language": repo.language,
        } if repo else None,
    }


@router.put("/active")
async def set_active(request: Request):
    """Set the active repository."""
    body = await request.json()
    repo_id = body.get("repo_id")
    if not repo_id:
        raise HTTPException(status_code=400, detail="repo_id is required")

    # Verify the repo exists in storage
    storage = _get_storage(request)
    bp_dir = Path(storage._base_path) / "blueprints" / repo_id
    if not bp_dir.exists():
        raise HTTPException(status_code=404, detail="Repository blueprint not found")

    profile_repo = await _get_profile_repo(request)
    await profile_repo.set_active_repo(repo_id)

    return {"active_repo_id": repo_id}


@router.delete("/active")
async def clear_active(request: Request):
    """Clear the active repository."""
    profile_repo = await _get_profile_repo(request)
    await profile_repo.set_active_repo(None)
    return {"active_repo_id": None}


# ---------------------------------------------------------------------------
# Agent files
# ---------------------------------------------------------------------------

@router.get("/repositories/{repo_id}/agent-files")
async def get_agent_files(repo_id: str, request: Request):
    """Generate and return CLAUDE.md, cursor rules, AGENTS.md, and per-folder CLAUDE.md files.

    Only works when a structured blueprint.json is available.
    """
    storage = _get_storage(request)
    blueprint = await _load_structured_blueprint(storage, repo_id)

    if not blueprint:
        raise HTTPException(
            status_code=404,
            detail="Structured blueprint (blueprint.json) not found. Re-analyze to generate.",
        )

    output = generate_all(blueprint)
    files = output.to_file_map()

    # Load pre-generated intent layer files, or generate on-demand as fallback
    try:
        il_base = f"blueprints/{repo_id}/intent_layer"
        if await storage.exists(f"{il_base}/CLAUDE.md") or await storage.exists(f"{il_base}/CODEBASE_MAP.md"):
            il_files = await storage.list_files(il_base)
            for file_path in il_files:
                rel_path = file_path[len(il_base) + 1:]
                if rel_path and rel_path not in files:
                    content = await storage.read(file_path)
                    text = content.decode("utf-8") if isinstance(content, bytes) else content
                    files[rel_path] = text
        else:
            il_service = request.app.container.intent_layer_service()
            il_output = await il_service.preview(source_repo_id=repo_id)
            for path, content in il_output.claude_md_files.items():
                if path not in files:
                    files[path] = content
            if il_output.codebase_map:
                files["CODEBASE_MAP.md"] = il_output.codebase_map
    except Exception as e:
        import logging
        logging.getLogger("intent_layer").error(f"Intent layer load failed: {e}", exc_info=True)

    return {
        "claude_md": output.claude_md,
        "cursor_rules": "\n\n".join(rf.render_cursor() for rf in output.rule_files),
        "agents_md": output.agents_md,
        "files": files,
    }


# ---------------------------------------------------------------------------
# Blueprint by repository ID
# ---------------------------------------------------------------------------

@router.get("/repositories/{repo_id}/blueprint")
async def get_repository_blueprint(
    repo_id: str,
    request: Request,
    format: str = "markdown",
):
    """Get the blueprint for a repository directly by repo_id.

    This is the workspace-oriented endpoint (no analysis_id needed).
    The structured blueprint.json is the single source of truth.
    """
    storage = _get_storage(request)
    blueprint = await _load_structured_blueprint(storage, repo_id)

    if not blueprint:
        raise HTTPException(
            status_code=404,
            detail="Structured blueprint (blueprint.json) not found for this repository.",
        )

    if format == "json":
        return {
            "repository_id": repo_id,
            "type": "backend",
            "format": "json",
            "structured": blueprint.model_dump(),
        }

    from application.services.blueprint_renderer import render_blueprint_markdown
    
    # Try to find the latest analysis ID to support debug/analysis-data view
    analysis_id = None
    try:
        analysis_repo = await _get_analysis_repo(request)
        latest = await analysis_repo.get_latest_by_repo_id(repo_id)
        if latest:
            analysis_id = latest.id
    except Exception:
        pass

    return {
        "repository_id": repo_id,
        "analysis_id": analysis_id,
        "type": "backend",
        "format": "markdown",
        "content": render_blueprint_markdown(blueprint),
    }


# ---------------------------------------------------------------------------
# Source file content
# ---------------------------------------------------------------------------

@router.get("/repositories/{repo_id}/source-files/{file_path:path}")
async def get_source_file(repo_id: str, file_path: str, request: Request):
    """Return the content of a source file from the persisted repository copy.

    The full repository is copied to persistent storage during analysis so
    files remain available after the temp clone is deleted.
    """
    # Reject path traversal
    if ".." in file_path:
        raise HTTPException(status_code=400, detail="Invalid file path")

    storage = _get_storage(request)
    repo_dir = Path(storage._base_path) / "repos" / repo_id

    if not repo_dir.is_dir():
        raise HTTPException(status_code=404, detail="No source files available for this repository")

    target = (repo_dir / file_path).resolve()

    # Ensure resolved path is still under repo_dir (prevent traversal)
    if not str(target).startswith(str(repo_dir.resolve())):
        raise HTTPException(status_code=400, detail="Invalid file path")

    if not target.is_file():
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")

    try:
        content = target.read_text(encoding="utf-8", errors="replace")
    except Exception:
        raise HTTPException(status_code=500, detail=f"Failed to read file: {file_path}")

    return {"file_path": file_path, "content": content}


# ---------------------------------------------------------------------------
# Delete repository analysis
# ---------------------------------------------------------------------------

@router.delete("/repositories/{repo_id}")
async def delete_repository(repo_id: str, request: Request):
    """Delete repository analysis data and storage files."""
    storage = _get_storage(request)
    bp_dir = Path(storage._base_path) / "blueprints" / repo_id

    # Remove storage files
    import shutil
    if bp_dir.exists():
        shutil.rmtree(bp_dir)

    # Also remove persisted repo copy
    repo_copy_dir = Path(storage._base_path) / "repos" / repo_id
    if repo_copy_dir.exists():
        shutil.rmtree(repo_copy_dir)

    # Delete DB row (CASCADE handles analyses, analysis_data, events, embeddings)
    try:
        repo_repo = await _get_repos(request)
        await repo_repo.delete(repo_id)
    except Exception:
        pass  # Graceful — storage is already cleaned up

    # Clear active repo if this was the active one
    profile_repo = await _get_profile_repo(request)
    profile = await profile_repo.get_default()
    if profile and profile.active_repo_id == repo_id:
        await profile_repo.set_active_repo(None)

    return {"deleted": True, "repo_id": repo_id}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _load_structured_blueprint(storage, repo_id: str) -> Optional[StructuredBlueprint]:
    """Load a structured blueprint.json for the given repository."""
    json_path = f"blueprints/{repo_id}/blueprint.json"
    try:
        if await storage.exists(json_path):
            content = await storage.read(json_path)
            text = content.decode("utf-8") if isinstance(content, bytes) else content
            data = json.loads(text)
            return StructuredBlueprint.model_validate(data)
    except Exception:
        pass
    return None
