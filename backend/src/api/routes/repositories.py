"""Repository routes."""
import asyncio
import logging
from fastapi import APIRouter, HTTPException, Header, Request
from typing import List, Optional
from api.dto.requests import StartAnalysisRequest
from api.dto.responses import RepositoryResponse, AnalysisResponse
from application.services.github_service import GitHubService
from config.settings import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/repositories", tags=["repositories"])

# Strong references to background tasks to prevent garbage collection.
# asyncio only keeps weak refs — without this, tasks can silently vanish.
_background_tasks: set[asyncio.Task] = set()


def resolve_github_token(request: Request) -> Optional[str]:
    """Resolve GitHub token: header first, then fall back to env GITHUB_TOKEN."""
    # 1. Check Authorization header (user-provided token)
    authorization = request.headers.get("Authorization", "")
    if authorization and authorization.startswith("Bearer "):
        header_token = authorization.replace("Bearer ", "").strip()
        if header_token:
            return header_token
    
    # 2. Fall back to server-side env token
    settings = get_settings()
    if settings.github_token and settings.github_token.strip():
        return settings.github_token.strip()
    
    return None


@router.get("/", response_model=List[RepositoryResponse])
async def list_repositories(request: Request):
    """List all user's repositories."""
    token = resolve_github_token(request)

    if not token:
        return []

    container = request.app.container
    github_service = container.github_service()

    try:
        repos = await github_service.list_repositories(token)
        return repos
    except Exception as e:
        from domain.exceptions.domain_exceptions import AuthorizationError

        if isinstance(e, AuthorizationError) or "401" in str(e) or "Bad credentials" in str(e):
            has_header = bool(request.headers.get("Authorization", ""))
            token_source = "user-provided" if has_header else "server environment"
            raise HTTPException(
                status_code=401,
                detail=f"GitHub token ({token_source}) is invalid or expired. Please check your token and re-authenticate."
            )

        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{owner}/{repo}/analyze", response_model=AnalysisResponse)
async def start_analysis(
    owner: str,
    repo: str,
    request: Request,
    analysis_request: StartAnalysisRequest | None = None,
):
    """Start analysis for a repository."""
    token = resolve_github_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="No GitHub token available. Set GITHUB_TOKEN in .env or provide a token.")

    # Get container
    container = request.app.container

    # Resolve DB client from container
    db = await container.db()

    from infrastructure.persistence.user_repository import UserRepository
    from infrastructure.persistence.repository_repository import RepositoryRepository
    from infrastructure.persistence.analysis_repository import AnalysisRepository
    from infrastructure.persistence.analysis_event_repository import AnalysisEventRepository

    user_repo = UserRepository(db=db)
    repo_repo = RepositoryRepository(db=db)
    analysis_repo = AnalysisRepository(db=db)
    event_repo = AnalysisEventRepository(db=db)

    # Create services with resolved repositories
    from application.services.repository_service import RepositoryService
    from application.services.analysis_service import AnalysisService
    from application.services.phased_blueprint_generator import PhasedBlueprintGenerator
    from infrastructure.analysis.structure_analyzer import StructureAnalyzer
    from config.settings import get_settings

    storage = container.storage()
    github_service = container.github_service()
    settings = get_settings()

    repo_service = RepositoryService(
        repository_repo=repo_repo,
        github_service=github_service,
        storage=storage,
    )

    # Create only what's needed for analysis
    structure_analyzer = StructureAnalyzer()

    # Pass db_client to enable RAG-based retrieval
    prompt_loader = container.database_prompt_loader()
    phased_blueprint_generator = PhasedBlueprintGenerator(
        settings=settings,
        db_client=db,
        prompt_loader=prompt_loader,
    )

    # Create analysis service (with intent layer so Phase 7 runs in-pipeline)
    intent_layer_service = container.intent_layer_service()
    analysis_service = AnalysisService(
        analysis_repo=analysis_repo,
        repository_repo=repo_repo,
        event_repo=event_repo,
        structure_analyzer=structure_analyzer,
        persistent_storage=storage,
        phased_blueprint_generator=phased_blueprint_generator,
        db_client=db,
        intent_layer_service=intent_layer_service,
    )
    
    try:
        # For now, use a fixed user ID since we don't have user management yet
        # Use a deterministic UUID for the default user
        import uuid
        user_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, "default-user"))
        
        # Ensure user exists (or create a dummy one for now)
        user = await user_repo.get_by_id(user_id)
        if not user:
            from domain.entities.user import User
            user = User.create(github_token_encrypted="dummy_encrypted_token")
            user.id = user_id # Force ID for default user
            await user_repo.add(user)

        # 1. Get or create repository record
        try:
            repository = await repo_service.get_repository_by_full_name(user_id, owner, repo)
            if not repository:
                repository = await repo_service.create_repository(user_id, token, owner, repo)
        except Exception as e:
            print(f"Error getting/creating repo: {str(e)}")
            import traceback
            traceback.print_exc()
            repository = await repo_service.create_repository(user_id, token, owner, repo)

        # 2. Start analysis
        prompt_config = analysis_request.prompt_config if analysis_request else None
        analysis = await analysis_service.start_analysis(repository.id, prompt_config)
        
        # 3. Run analysis via ARQ worker (preferred) or in-process fallback
        arq_pool = await container.arq_pool()
        logger.info("ARQ pool resolved: %s (type=%s)", arq_pool is not None, type(arq_pool).__name__)

        redis_available = False
        if arq_pool is not None:
            try:
                await arq_pool.ping()
                redis_available = True
            except Exception as ping_err:
                logger.warning("Redis unreachable (%s), falling back to in-process analysis", ping_err)

        if redis_available:
            # Enqueue to ARQ worker
            try:
                job = await arq_pool.enqueue_job(
                    "analyze_repository",
                    analysis_id=analysis.id,
                    repository_id=repository.id,
                    token=token,
                    prompt_config=prompt_config,
                )
                if job is None:
                    analysis.fail("Job was not enqueued (possible duplicate)")
                    await analysis_repo.update(analysis)
                    raise HTTPException(status_code=409, detail="Analysis job was not enqueued — a duplicate may already be running")
                logger.info("Job enqueued: id=%s, analysis=%s", job.job_id, analysis.id)
            except HTTPException:
                raise
            except Exception as queue_err:
                logger.exception("Failed to enqueue job for analysis %s", analysis.id)
                analysis.fail(f"Failed to queue: {queue_err}")
                await analysis_repo.update(analysis)
                raise HTTPException(status_code=500, detail=f"Task queue error: {queue_err}")
        else:
            # No Redis — run analysis in-process as a background asyncio task
            logger.info("Running analysis %s in-process (no Redis)", analysis.id)
            task = asyncio.create_task(
                _run_analysis_in_process(
                    container=container,
                    analysis_service=analysis_service,
                    repo_service=repo_service,
                    analysis_id=analysis.id,
                    repository_id=repository.id,
                    token=token,
                    prompt_config=prompt_config,
                )
            )
            _background_tasks.add(task)
            task.add_done_callback(_background_tasks.discard)
        
        return analysis
    except Exception as e:
        logger.exception("Error in start_analysis")
        raise HTTPException(status_code=500, detail=str(e))


async def _run_analysis_in_process(
    container,
    analysis_service,
    repo_service,
    analysis_id: str,
    repository_id: str,
    token: str,
    prompt_config: dict | None = None,
) -> None:
    """Run analysis as an in-process background task (no Redis/ARQ needed)."""
    from pathlib import Path
    from infrastructure.persistence.analysis_repository import AnalysisRepository
    from infrastructure.storage.temp_storage import TempStorage

    db = await container.db()
    analysis_repo = AnalysisRepository(db=db)
    temp_storage = TempStorage()
    temp_dir = temp_storage.get_base_path()

    try:
        repo = await repo_service.get_repository(repository_id)
        if not repo:
            raise ValueError(f"Repository {repository_id} not found")

        repo_path = await repo_service.clone_repository(repo, token, temp_dir)
        repo_path = Path(repo_path).resolve()

        await analysis_service.run_analysis(
            analysis_id=analysis_id,
            repo_path=repo_path,
            token=token,
            prompt_config=prompt_config,
        )
        logger.info("In-process analysis %s completed", analysis_id)
    except Exception as e:
        logger.exception("In-process analysis %s failed", analysis_id)
        try:
            analysis = await analysis_repo.get_by_id(analysis_id)
            if analysis and analysis.status != "failed":
                analysis.fail(str(e))
                await analysis_repo.update(analysis)
        except Exception:
            pass
    finally:
        try:
            await repo_service.cleanup_temp_repository(temp_dir)
        except Exception:
            pass


