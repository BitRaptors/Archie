"""Analysis routes."""
from fastapi import APIRouter, HTTPException, Request
from sse_starlette.sse import EventSourceResponse
from typing import List, Optional
from api.dto.responses import AnalysisResponse, AnalysisEventResponse
from domain.interfaces.repositories import IAnalysisRepository, IAnalysisEventRepository
from domain.entities.blueprint import StructuredBlueprint
from infrastructure.persistence.analysis_repository import AnalysisRepository
from infrastructure.persistence.analysis_event_repository import AnalysisEventRepository
from application.services.analysis_data_collector import analysis_data_collector
import asyncio
import json

router = APIRouter(prefix="/analyses", tags=["analyses"])


async def get_analysis_repo(request: Request) -> IAnalysisRepository:
    """Get analysis repository with resolved dependencies."""
    db = await request.app.container.db()
    return AnalysisRepository(db=db)


async def get_event_repo(request: Request) -> IAnalysisEventRepository:
    """Get analysis event repository with resolved dependencies."""
    db = await request.app.container.db()
    return AnalysisEventRepository(db=db)


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

            # Handle Analysis Data
            analysis_data = await analysis_data_collector.get_data(analysis_id)

            # Send gathered data once
            if analysis_data.get("gathered") and not sent_gathered:
                yield {
                    "event": "gathered",
                    "data": json.dumps(analysis_data["gathered"]),
                }
                sent_gathered = True

            # Send new phases
            for phase_info in analysis_data.get("phases", []):
                phase_name = phase_info["phase"]
                if phase_name not in sent_phases:
                    yield {
                        "event": "phase",
                        "data": json.dumps(phase_info),
                    }
                    sent_phases.add(phase_name)

            # Check if analysis is complete - send final event and break
            if analysis.status in ["completed", "failed"]:
                if not sent_completion:
                    # Final analysis data check
                    analysis_data = await analysis_data_collector.get_data(analysis_id)
                    yield {
                        "event": "analysis_complete",
                        "data": json.dumps(analysis_data),
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


@router.get("/{analysis_id}/analysis-data")
async def get_analysis_data(
    analysis_id: str,
    request: Request,
):
    """Get analysis data for a completed analysis.
    
    This endpoint returns the collected information from the analysis process,
    including gathered data, phase data, and summary metrics.
    
    Args:
        analysis_id: ID of the analysis
        
    Returns:
        Analysis data dict with gathered, phases, and summary
    """
    analysis_repo = await get_analysis_repo(request)
    analysis = await analysis_repo.get_by_id(analysis_id)
    
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    
    # Get analysis data from Supabase
    analysis_data = await analysis_data_collector.get_data(analysis_id)
    
    return analysis_data


@router.get("/{analysis_id}/agent-files")
async def get_agent_files(
    analysis_id: str,
    request: Request,
):
    """Get the commit-ready file tree for an analysis.

    Returns CLAUDE.md, AGENTS.md, rules, per-folder CLAUDE.md, CODEBASE_MAP.md.
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

    container = request.app.container
    storage = container.storage()
    files: dict[str, str] = {}

    # Try loading pre-generated intent layer files (includes everything since consolidation)
    try:
        il_base = f"blueprints/{analysis.repository_id}/intent_layer"
        if await storage.exists(f"{il_base}/CLAUDE.md"):
            il_files = await storage.list_files(il_base)
            for file_path in il_files:
                rel_path = file_path[len(il_base) + 1:]
                if rel_path:
                    content = await storage.read(file_path)
                    text = content.decode("utf-8") if isinstance(content, bytes) else content
                    files[rel_path] = text
    except Exception:
        pass

    # Fallback: generate on-demand via intent layer service
    if not files:
        il_service = container.intent_layer_service()
        try:
            il_output = await il_service.preview(source_repo_id=analysis.repository_id)
            files = il_output.claude_md_files
        except Exception as e:
            import logging
            logging.getLogger("intent_layer").error(f"Intent layer generation failed: {e}", exc_info=True)
            raise HTTPException(status_code=404, detail="Could not generate agent files. Blueprint may be missing.")

    # Always include Claude Code hooks (static, not analysis-dependent)
    from application.services.hook_assets import get_hook_files
    for path, content in get_hook_files().items():
        if path not in files:
            files[path] = content

    # Backward-compatible response shape
    cursor_rules_parts = [v for k, v in sorted(files.items()) if k.startswith(".cursor/rules/")]
    return {
        "claude_md": files.get("CLAUDE.md", ""),
        "cursor_rules": "\n\n".join(cursor_rules_parts),
        "agents_md": files.get("AGENTS.md", ""),
        "files": files,
    }


async def _load_structured_blueprint(storage, repository_id: str) -> StructuredBlueprint | None:
    """Try to load the structured JSON blueprint from storage."""
    json_path = f"blueprints/{repository_id}/blueprint.json"
    try:
        if await storage.exists(json_path):
            content = await storage.read(json_path)
            text = content.decode("utf-8") if isinstance(content, bytes) else content
            data = json.loads(text)
            return StructuredBlueprint.model_validate(data)
    except Exception:
        pass
    return None




@router.get("/{analysis_id}/blueprint")
async def get_blueprint(
    analysis_id: str,
    request: Request,
    type: Optional[str] = "backend",
    format: Optional[str] = "markdown",
):
    """Get generated blueprint for an analysis.
    
    Args:
        analysis_id: ID of the analysis
        type: Type of blueprint to fetch ("backend" or "frontend"), defaults to "backend"
        format: Output format ("markdown" for human-readable, "json" for structured), defaults to "markdown"
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
            "content": "# Frontend Archie Blueprint\n\n**Coming Soon**\n\nThe frontend analysis engine is currently being developed. Once implemented, this section will contain a deep dive into the frontend architecture, including component patterns, state management, and more.",
            "path": f"blueprints/{analysis.repository_id}/frontend_blueprint.md"
        }
    
    # Load the structured blueprint (single source of truth)
    blueprint = await _load_structured_blueprint(storage, analysis.repository_id)
    if not blueprint:
        raise HTTPException(
            status_code=404,
            detail="Structured blueprint (blueprint.json) not found. Re-analyze to generate.",
        )
    
    # JSON format: return the raw model
    if format == "json":
        return {
            "analysis_id": analysis_id,
            "repository_id": analysis.repository_id,
            "type": "backend",
            "format": "json",
            "structured": blueprint.model_dump(),
        }
    
    # Markdown format: render on-the-fly from JSON
    from application.services.blueprint_renderer import render_blueprint_markdown
    blueprint_content = render_blueprint_markdown(blueprint)
    
    return {
        "analysis_id": analysis_id,
        "repository_id": analysis.repository_id,
        "type": "backend",
        "format": "markdown",
        "content": blueprint_content,
    }
