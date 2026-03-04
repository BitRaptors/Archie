"""Delivery routes -- push architecture outputs to a target GitHub repository."""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from api.routes.repositories import resolve_github_token
from application.services.delivery_service import DeliveryService, VALID_OUTPUTS

router = APIRouter(prefix="/delivery", tags=["delivery"])


# ---------------------------------------------------------------------------
# Request / Response DTOs
# ---------------------------------------------------------------------------

class ApplyRequest(BaseModel):
    source_repo_id: str
    target_repo: str  # "owner/repo"
    strategy: str = "pr"
    outputs: list[str] = ["claude_md", "claude_rules", "cursor_rules", "agents_md", "mcp_claude", "mcp_cursor", "intent_layer", "codebase_map"]
    branch_prefix: str = "gbr"


class PreviewRequest(BaseModel):
    source_repo_id: str
    outputs: list[str] = ["claude_md", "claude_rules", "cursor_rules", "agents_md", "mcp_claude", "mcp_cursor", "intent_layer", "codebase_map"]


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
    """Generate architecture outputs and push them to a target GitHub repository."""
    token = resolve_github_token(request)
    if not token:
        raise HTTPException(
            status_code=401,
            detail="GitHub token required. Set GITHUB_TOKEN in env or pass Authorization header.",
        )

    service = _get_delivery_service(request)
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
