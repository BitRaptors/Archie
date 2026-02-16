"""Prompt management routes."""
from fastapi import APIRouter, HTTPException, Request
from api.dto.requests import UpdatePromptRequest
from api.dto.responses import PromptResponse, PromptRevisionResponse
from infrastructure.persistence.supabase_adapter import SupabaseAdapter
from infrastructure.persistence.prompt_repository import PromptRepository
from infrastructure.persistence.prompt_revision_repository import PromptRevisionRepository
from infrastructure.prompts.database_prompt_loader import DatabasePromptLoader
from application.services.prompt_service import PromptService

router = APIRouter(prefix="/prompts", tags=["prompts"])


async def _get_prompt_service(request: Request) -> PromptService:
    """Resolve PromptService by manually constructing dependencies.

    The DI container returns Futures for providers that depend on the async
    supabase_client Resource, so we resolve the client first, then build
    the chain ourselves — same pattern used by analyses.py / workspace.py.
    """
    container = request.app.container
    supabase_client = await container.supabase_client()
    db = SupabaseAdapter(supabase_client)
    prompt_repo = PromptRepository(db=db)
    revision_repo = PromptRevisionRepository(db=db)
    prompt_loader = DatabasePromptLoader(prompt_repo)
    return PromptService(
        prompt_repo=prompt_repo,
        revision_repo=revision_repo,
        prompt_loader=prompt_loader,
    )


@router.get("/", response_model=list[PromptResponse])
async def list_prompts(request: Request):
    """List all default prompts."""
    svc = await _get_prompt_service(request)
    prompts = await svc.get_all_prompts()
    return [PromptResponse(**p.__dict__) for p in prompts]


@router.get("/{prompt_id}", response_model=PromptResponse)
async def get_prompt(prompt_id: str, request: Request):
    """Get a single prompt by ID."""
    svc = await _get_prompt_service(request)
    try:
        prompt = await svc.get_prompt(prompt_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return PromptResponse(**prompt.__dict__)


@router.put("/{prompt_id}", response_model=PromptResponse)
async def update_prompt(
    prompt_id: str,
    body: UpdatePromptRequest,
    request: Request,
):
    """Update a prompt (creates a revision of the previous state)."""
    svc = await _get_prompt_service(request)
    try:
        updated = await svc.update_prompt(
            prompt_id=prompt_id,
            name=body.name,
            description=body.description,
            prompt_template=body.prompt_template,
            variables=body.variables,
            change_summary=body.change_summary,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return PromptResponse(**updated.__dict__)


@router.get("/{prompt_id}/revisions", response_model=list[PromptRevisionResponse])
async def list_revisions(prompt_id: str, request: Request):
    """List revision history for a prompt."""
    svc = await _get_prompt_service(request)
    try:
        revisions = await svc.get_revision_history(prompt_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return [PromptRevisionResponse(**r.__dict__) for r in revisions]


@router.post("/{prompt_id}/revert/{revision_id}", response_model=PromptResponse)
async def revert_prompt(prompt_id: str, revision_id: str, request: Request):
    """Revert a prompt to a previous revision."""
    svc = await _get_prompt_service(request)
    try:
        reverted = await svc.revert_to_revision(prompt_id, revision_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return PromptResponse(**reverted.__dict__)
