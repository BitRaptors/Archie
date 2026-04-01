"""Delivery routes -- push architecture outputs to a target GitHub repository or local path."""
import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from api.routes.repositories import resolve_github_token
from application.services.delivery_service import DeliveryService, VALID_OUTPUTS

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/delivery", tags=["delivery"])

# Keep references to background tasks so they aren't garbage-collected
_background_tasks: set[asyncio.Task] = set()  # type: ignore[type-arg]


# ---------------------------------------------------------------------------
# Request / Response DTOs
# ---------------------------------------------------------------------------

class ApplyRequest(BaseModel):
    source_repo_id: str
    target_repo: Optional[str] = None  # "owner/repo" — required for pr/commit
    strategy: str = "pr"
    outputs: list[str] = ["claude_md", "claude_rules", "cursor_rules", "agents_md", "mcp_claude", "mcp_cursor", "intent_layer", "codebase_map", "claude_hooks"]
    branch_prefix: str = "feature/archi"
    target_local_path: Optional[str] = None  # required for local strategy


class PreviewRequest(BaseModel):
    source_repo_id: str
    outputs: list[str] = ["claude_md", "claude_rules", "cursor_rules", "agents_md", "mcp_claude", "mcp_cursor", "intent_layer", "codebase_map", "claude_hooks"]


class SmartRefreshRequest(BaseModel):
    repo_id: str
    changed_files: list[str]
    target_local_path: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_delivery_service(request: Request) -> DeliveryService:
    container = request.app.container
    return container.delivery_service()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/preview")
async def preview(body: PreviewRequest, request: Request):
    """Preview generated outputs without pushing to GitHub."""
    service = _get_delivery_service(request)
    try:
        result = await service.preview(body.source_repo_id, body.outputs)
        return result
    except Exception as e:
        from domain.exceptions.domain_exceptions import ValidationError
        if isinstance(e, ValidationError):
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/apply")
async def apply(body: ApplyRequest, request: Request):
    """Generate architecture outputs and push them to a target GitHub repository or local path."""
    service = _get_delivery_service(request)

    if body.strategy == "local":
        if not body.target_local_path:
            raise HTTPException(status_code=400, detail="target_local_path is required for local strategy.")
        try:
            result = await service.apply(
                source_repo_id=body.source_repo_id,
                target_repo_full_name="",
                token="",
                outputs=body.outputs,
                strategy="local",
                target_local_path=body.target_local_path,
            )
            return {
                "status": result.status,
                "strategy": result.strategy,
                "pr_url": result.pr_url,
                "commit_sha": result.commit_sha,
                "branch": result.branch,
                "files_delivered": result.files_delivered,
            }
        except Exception as e:
            from domain.exceptions.domain_exceptions import ValidationError as VE
            if isinstance(e, VE):
                raise HTTPException(status_code=400, detail=str(e))
            raise HTTPException(status_code=500, detail=str(e))

    # GitHub strategies (pr / commit)
    if not body.target_repo:
        raise HTTPException(status_code=400, detail="target_repo is required for pr/commit strategy.")

    token = resolve_github_token(request)
    if not token:
        raise HTTPException(
            status_code=401,
            detail="GitHub token required. Set GITHUB_TOKEN in env or pass Authorization header.",
        )

    try:
        result = await service.apply(
            source_repo_id=body.source_repo_id,
            target_repo_full_name=body.target_repo,
            token=token,
            outputs=body.outputs,
            strategy=body.strategy,
            branch_prefix=body.branch_prefix,
        )
        return {
            "status": result.status,
            "strategy": result.strategy,
            "pr_url": result.pr_url,
            "commit_sha": result.commit_sha,
            "branch": result.branch,
            "files_delivered": result.files_delivered,
        }
    except Exception as e:
        from domain.exceptions.domain_exceptions import ValidationError, AuthorizationError
        if isinstance(e, AuthorizationError):
            raise HTTPException(status_code=401, detail=str(e))
        if isinstance(e, ValidationError):
            raise HTTPException(status_code=400, detail=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/smart-refresh")
async def smart_refresh(body: SmartRefreshRequest, request: Request):
    """Evaluate code changes against the architecture blueprint.

    Phase 1 (synchronous): evaluate alignment and return warnings + stale list.
    Phase 2 (background): regenerate CLAUDE.md for stale folders if any.
    """
    service = await request.app.container.smart_refresh_service()
    try:
        result = await service.refresh(
            repo_id=body.repo_id,
            changed_files=body.changed_files,
            target_local_path=body.target_local_path,
        )

        # Fire-and-forget regeneration in background
        if result.stale_folders:
            task = asyncio.create_task(
                service.regenerate_stale(
                    repo_id=body.repo_id,
                    stale_folders=result.stale_folders,
                    target_local_path=body.target_local_path,
                    changed_files=body.changed_files,
                )
            )
            _background_tasks.add(task)
            task.add_done_callback(_background_tasks.discard)
            logger.info(
                "Dispatched background regeneration for %d stale folder(s)",
                len(result.stale_folders),
            )

        return result.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
