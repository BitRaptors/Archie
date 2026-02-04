"""Analysis routes."""
from fastapi import APIRouter, HTTPException, Request
from sse_starlette.sse import EventSourceResponse
from typing import List, Optional
from api.dto.responses import AnalysisResponse, AnalysisEventResponse
from domain.interfaces.repositories import IAnalysisRepository, IAnalysisEventRepository
from config.container import Container
from infrastructure.persistence.analysis_repository import SupabaseAnalysisRepository
from infrastructure.persistence.analysis_event_repository import SupabaseAnalysisEventRepository
from application.services.debug_collector import debug_collector
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
        sent_completion = False
        sent_phases = set()
        sent_gathered = False
        
        while True:
            # Check if client disconnected
            if await request.is_disconnected():
                break

            # Get latest analysis state
            analysis = await analysis_repo.get_by_id(analysis_id)
            if not analysis:
                yield {"event": "error", "data": json.dumps({"message": "Analysis not found"})}
                break

            # Send current status
            yield {
                "event": "status",
                "data": json.dumps({
                    "status": analysis.status,
                    "progress": analysis.progress_percentage,
                }),
            }

            # Handle Debug Data
            debug_data = debug_collector.get_data(analysis_id)
            
            # Send gathered data once
            if debug_data.get("gathered") and not sent_gathered:
                yield {
                    "event": "debug_gathered",
                    "data": json.dumps(debug_data["gathered"]),
                }
                sent_gathered = True
                
            # Send new phases
            for phase_info in debug_data.get("phases", []):
                phase_name = phase_info["phase"]
                if phase_name not in sent_phases:
                    yield {
                        "event": "debug_phase",
                        "data": json.dumps(phase_info),
                    }
                    sent_phases.add(phase_name)

            # Check if analysis is complete - send final event and break
            if analysis.status in ["completed", "failed"]:
                if not sent_completion:
                    # Final debug data check
                    debug_data = debug_collector.get_data(analysis_id)
                    yield {
                        "event": "debug_complete",
                        "data": json.dumps(debug_data),
                    }
                    
                    # Send any remaining events first
                    events = await event_repo.get_by_analysis_id(analysis_id)
                    if last_event_id:
                        found = False
                        for e in events:
                            if found:
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
                            if e.id == last_event_id:
                                found = True
                    
                    # Send completion event
                    yield {
                        "event": "complete",
                        "data": json.dumps({
                            "status": analysis.status,
                            "progress": analysis.progress_percentage,
                        }),
                    }
                    sent_completion = True
                    # Keep connection open briefly to allow client to receive completion event
                    # Client should close connection on receiving 'complete' event
                    await asyncio.sleep(1)
                # Exit loop - connection will close naturally
                break

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

            await asyncio.sleep(2)
    
    return EventSourceResponse(event_generator())


@router.get("/{analysis_id}/blueprint")
async def get_blueprint(
    analysis_id: str,
    request: Request,
    type: Optional[str] = "backend",
):
    """Get generated blueprint for an analysis.
    
    Args:
        analysis_id: ID of the analysis
        type: Type of blueprint to fetch ("backend" or "frontend"), defaults to "backend"
    """
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
    
    # Determine blueprint path based on type
    if type == "frontend":
        # Frontend analysis not implemented yet - return honeypot
        return {
            "analysis_id": analysis_id,
            "repository_id": analysis.repository_id,
            "type": "frontend",
            "content": "# Frontend Architecture Blueprint\n\n**Coming Soon**\n\nThe frontend analysis engine is currently being developed. Once implemented, this section will contain a deep dive into the frontend architecture, including component patterns, state management, and more.",
            "path": f"blueprints/{analysis.repository_id}/frontend_blueprint.md"
        }
    
    # Backend blueprint path
    blueprint_path = f"blueprints/{analysis.repository_id}/backend_blueprint.md"
    blueprint_type = "backend"
    
    # If new path doesn't exist, check old path (treat old blueprint.md as backend_blueprint.md)
    if not await storage.exists(blueprint_path):
        old_path = f"blueprints/{analysis.repository_id}/blueprint.md"
        if await storage.exists(old_path):
            blueprint_path = old_path
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Backend blueprint not found at: {blueprint_path}"
            )
    
    try:
        blueprint_content_bytes = await storage.read(blueprint_path)
        # Decode bytes to string if needed
        if isinstance(blueprint_content_bytes, bytes):
            blueprint_content = blueprint_content_bytes.decode('utf-8')
        else:
            blueprint_content = blueprint_content_bytes
    except Exception as e:
        raise HTTPException(
            status_code=404, 
            detail=f"Error reading backend blueprint from {blueprint_path}: {str(e)}"
        )
    
    return {
        "analysis_id": analysis_id,
        "repository_id": analysis.repository_id,
        "type": blueprint_type,
        "content": blueprint_content,
        "path": blueprint_path,
    }
