"""Analysis routes."""
from fastapi import APIRouter, HTTPException, Request
from sse_starlette.sse import EventSourceResponse
from typing import List, Optional
from api.dto.responses import AnalysisResponse, AnalysisEventResponse
from domain.interfaces.repositories import IAnalysisRepository, IAnalysisEventRepository
from config.container import Container
from infrastructure.persistence.analysis_repository import SupabaseAnalysisRepository
from infrastructure.persistence.analysis_event_repository import SupabaseAnalysisEventRepository
import asyncio
import json

router = APIRouter(prefix="/analyses", tags=["analyses"])


async def get_analysis_repo(request: Request) -> IAnalysisRepository:
    """Get analysis repository with resolved dependencies."""
    container = request.app.container
    supabase_client = await container.supabase_client()
    return SupabaseAnalysisRepository(client=supabase_client)


async def get_event_repo(request: Request) -> IAnalysisEventRepository:
    """Get analysis event repository with resolved dependencies."""
    container = request.app.container
    supabase_client = await container.supabase_client()
    return SupabaseAnalysisEventRepository(client=supabase_client)


@router.get("/", response_model=List[AnalysisResponse])
async def list_analyses(
    request: Request,
    repository_id: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
):
    """List all analyses."""
    analysis_repo = await get_analysis_repo(request)
    if repository_id:
        # For now, just return all since we don't have filtered query in interface yet
        # or implement it in the repository
        analyses = await analysis_repo.get_all(limit=limit, offset=offset)
        return [a for a in analyses if a.repository_id == repository_id]
    
    return await analysis_repo.get_all(limit=limit, offset=offset)


@router.get("/{analysis_id}", response_model=AnalysisResponse)
async def get_analysis(
    analysis_id: str,
    request: Request,
):
    """Get analysis details."""
    analysis_repo = await get_analysis_repo(request)
    analysis = await analysis_repo.get_by_id(analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return analysis


@router.get("/{analysis_id}/events", response_model=List[AnalysisEventResponse])
async def get_analysis_events(
    analysis_id: str,
    request: Request,
):
    """Get all events for an analysis."""
    event_repo = await get_event_repo(request)
    return await event_repo.get_by_analysis_id(analysis_id)


@router.get("/{analysis_id}/stream")
async def stream_analysis_progress(
    analysis_id: str,
    request: Request,
):
    """Stream analysis progress and events via SSE."""
    analysis_repo = await get_analysis_repo(request)
    event_repo = await get_event_repo(request)
    
    async def event_generator():
        last_event_id = None
        while True:
            # Check if client disconnected
            if await request.is_disconnected():
                break

            # Get latest analysis state
            analysis = await analysis_repo.get_by_id(analysis_id)
            if not analysis:
                yield {"event": "error", "data": "Analysis not found"}
                break

            # Send current status
            yield {
                "event": "status",
                "data": json.dumps({
                    "status": analysis.status,
                    "progress": analysis.progress_percentage,
                }),
            }

            # Get new events
            events = await event_repo.get_by_analysis_id(analysis_id)
            new_events = []
            if last_event_id:
                # Find events after last_event_id
                found = False
                for e in events:
                    if found:
                        new_events.append(e)
                    if e.id == last_event_id:
                        found = True
            else:
                new_events = events

            for e in new_events:
                yield {
                    "event": "log",
                    "data": json.dumps({
                        "id": e.id,
                        "type": e.event_type,
                        "message": e.message,
                        "created_at": e.created_at.isoformat(),
                    }),
                }
                last_event_id = e.id

            if analysis.status in ["completed", "failed"]:
                break

            await asyncio.sleep(2)
    
    return EventSourceResponse(event_generator())


@router.get("/{analysis_id}/blueprint")
async def get_blueprint(
    analysis_id: str,
    request: Request,
):
    """Get generated blueprint for an analysis (basic blueprint, backward compatible)."""
    analysis_repo = await get_analysis_repo(request)
    analysis = await analysis_repo.get_by_id(analysis_id)
    
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    if analysis.status != "completed":
        raise HTTPException(
            status_code=400, 
            detail=f"Analysis is not completed. Current status: {analysis.status}"
        )
    
    # Get storage from container
    container = request.app.container
    storage = container.storage()
    
    # Blueprint is stored at: blueprints/{repository_id}/blueprint.md
    blueprint_path = f"blueprints/{analysis.repository_id}/blueprint.md"
    
    try:
        blueprint_content_bytes = await storage.read(blueprint_path)
        # Decode bytes to string if needed
        if isinstance(blueprint_content_bytes, bytes):
            blueprint_content = blueprint_content_bytes.decode('utf-8')
        else:
            blueprint_content = blueprint_content_bytes
        
        return {
            "analysis_id": analysis_id,
            "repository_id": analysis.repository_id,
            "content": blueprint_content,
            "path": blueprint_path,
        }
    except Exception as e:
        raise HTTPException(
            status_code=404, 
            detail=f"Blueprint not found: {str(e)}"
        )


@router.get("/{analysis_id}/blueprint/backend")
async def get_backend_blueprint(
    analysis_id: str,
    request: Request,
):
    """Get backend architecture blueprint for an analysis."""
    analysis_repo = await get_analysis_repo(request)
    analysis = await analysis_repo.get_by_id(analysis_id)
    
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    if analysis.status != "completed":
        raise HTTPException(
            status_code=400, 
            detail=f"Analysis is not completed. Current status: {analysis.status}"
        )
    
    # Get storage from container
    container = request.app.container
    storage = container.storage()
    
    # Backend blueprint is stored at: blueprints/{repository_id}/backend_blueprint.md
    blueprint_path = f"blueprints/{analysis.repository_id}/backend_blueprint.md"
    
    try:
        blueprint_content_bytes = await storage.read(blueprint_path)
        # Decode bytes to string if needed
        if isinstance(blueprint_content_bytes, bytes):
            blueprint_content = blueprint_content_bytes.decode('utf-8')
        else:
            blueprint_content = blueprint_content_bytes
        
        return {
            "analysis_id": analysis_id,
            "repository_id": analysis.repository_id,
            "type": "backend",
            "content": blueprint_content,
            "path": blueprint_path,
        }
    except Exception as e:
        raise HTTPException(
            status_code=404, 
            detail=f"Backend blueprint not found. This may be a frontend-only repository. Error: {str(e)}"
        )


@router.get("/{analysis_id}/blueprint/frontend")
async def get_frontend_blueprint(
    analysis_id: str,
    request: Request,
):
    """Get frontend architecture blueprint for an analysis."""
    analysis_repo = await get_analysis_repo(request)
    analysis = await analysis_repo.get_by_id(analysis_id)
    
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    if analysis.status != "completed":
        raise HTTPException(
            status_code=400, 
            detail=f"Analysis is not completed. Current status: {analysis.status}"
        )
    
    # Get storage from container
    container = request.app.container
    storage = container.storage()
    
    # Frontend blueprint is stored at: blueprints/{repository_id}/frontend_blueprint.md
    blueprint_path = f"blueprints/{analysis.repository_id}/frontend_blueprint.md"
    
    try:
        blueprint_content_bytes = await storage.read(blueprint_path)
        # Decode bytes to string if needed
        if isinstance(blueprint_content_bytes, bytes):
            blueprint_content = blueprint_content_bytes.decode('utf-8')
        else:
            blueprint_content = blueprint_content_bytes
        
        return {
            "analysis_id": analysis_id,
            "repository_id": analysis.repository_id,
            "type": "frontend",
            "content": blueprint_content,
            "path": blueprint_path,
        }
    except Exception as e:
        raise HTTPException(
            status_code=404, 
            detail=f"Frontend blueprint not found. This may be a backend-only repository. Error: {str(e)}"
        )
