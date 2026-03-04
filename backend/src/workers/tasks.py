"""Background task definitions."""
from arq.connections import RedisSettings
from pathlib import Path
from application.services.analysis_service import AnalysisService
from application.services.repository_service import RepositoryService
from application.services.analysis_data_collector import analysis_data_collector
from config.settings import get_settings
from config.container import Container
from infrastructure.persistence.user_repository import UserRepository
from infrastructure.persistence.repository_repository import RepositoryRepository
from infrastructure.persistence.analysis_repository import AnalysisRepository
from infrastructure.persistence.analysis_event_repository import AnalysisEventRepository
from infrastructure.analysis.structure_analyzer import StructureAnalyzer
from infrastructure.storage.temp_storage import TempStorage
from infrastructure.persistence.prompt_repository import PromptRepository
from infrastructure.prompts.database_prompt_loader import DatabasePromptLoader
from application.services.phased_blueprint_generator import PhasedBlueprintGenerator


async def startup(ctx):
    """Worker startup hook."""
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    print("Worker startup: Initializing container...")
    container = Container()
    # Initialize async resources
    await container.init_resources()
    print("Worker startup: Resources initialized")

    # Resolve DB client from container (backend-agnostic)
    db = await container.db()
    print(f"Worker startup: DB client resolved: {type(db)}")

    # Initialize analysis_data_collector with DB client for cross-process persistence
    analysis_data_collector.initialize(db)
    print("Worker startup: Analysis data collector initialized")

    # Create repositories using DB abstraction
    user_repo = UserRepository(db=db)
    repo_repo = RepositoryRepository(db=db)
    analysis_repo = AnalysisRepository(db=db)
    event_repo = AnalysisEventRepository(db=db)
    print(f"Worker startup: Repositories created: {type(repo_repo)}")

    # Create services with resolved repositories
    storage = container.storage()
    github_service = container.github_service()
    print(f"Worker startup: Storage: {type(storage)}, GitHub service: {type(github_service)}")

    repo_service = RepositoryService(
        repository_repo=repo_repo,
        github_service=github_service,
        storage=storage,
    )
    print(f"Worker startup: Repository service created: {type(repo_service)}")

    # Initialize only what's needed for phased blueprint generation
    structure_analyzer = StructureAnalyzer()
    settings = get_settings()

    # Build DB-backed prompt loader for the worker
    prompt_repo = PromptRepository(db=db)
    prompt_loader = DatabasePromptLoader(prompt_repo)

    # Pass db_client to enable RAG-based retrieval
    phased_blueprint_generator = PhasedBlueprintGenerator(
        settings=settings,
        db_client=db,
        prompt_loader=prompt_loader,
    )

    print(f"Worker startup: Analysis infrastructure initialized with RAG enabled")

    # Build intent layer service so Phase 7 runs in-pipeline
    from application.services.intent_layer_service import IntentLayerService
    intent_layer_service = IntentLayerService(storage=storage, settings=settings)

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
    print(f"Worker startup: Analysis service created: {type(analysis_service)}")

    # Store services in context - ensure they're actual objects, not Futures
    ctx["container"] = container
    ctx["analysis_service"] = analysis_service
    ctx["repository_service"] = repo_service

    # Verify they're stored correctly
    print(f"Worker startup: Stored repo_service type: {type(ctx['repository_service'])}")
    print("Worker startup: Complete")


async def shutdown(ctx):
    """Worker shutdown hook."""
    if "container" in ctx:
        await ctx["container"].shutdown_resources()


async def analyze_repository(ctx, analysis_id: str, repository_id: str, token: str, prompt_config: dict | None = None):
    """Background task to analyze a repository."""
    import asyncio
    import os

    print(f"analyze_repository: Starting analysis {analysis_id} for repository {repository_id}")

    # Get services from context
    analysis_service = ctx.get("analysis_service")
    repo_service = ctx.get("repository_service")
    container = ctx.get("container")

    if not repo_service:
        raise ValueError("repository_service not found in context")
    if not analysis_service:
        raise ValueError("analysis_service not found in context")
    if asyncio.iscoroutine(repo_service) or isinstance(repo_service, asyncio.Future):
        raise ValueError(f"repository_service is a Future/coroutine, not a service: {type(repo_service)}")

    # Get analysis repository to update status on errors
    db = await container.db()
    analysis_repo = AnalysisRepository(db=db)

    # Helper: robustly mark analysis as failed with retry
    async def _mark_failed(error_msg: str) -> None:
        for attempt in range(3):
            try:
                analysis = await analysis_repo.get_by_id(analysis_id)
                if analysis and analysis.status != "failed":
                    analysis.fail(error_msg)
                    await analysis_repo.update(analysis)
                return
            except Exception as update_err:
                print(f"analyze_repository: Failed to mark analysis as failed (attempt {attempt + 1}): {update_err}")
                if attempt < 2:
                    await asyncio.sleep(1)

    # Helper: log event with error swallowing (don't let logging failures crash the task)
    async def _safe_log(event_type: str, message: str) -> None:
        try:
            await analysis_service._log_event(analysis_id, event_type, message)
        except Exception as log_err:
            print(f"analyze_repository: Failed to log event: {log_err}")

    # Use temporary storage for cloning
    temp_storage = TempStorage()
    temp_dir = temp_storage.get_base_path()

    # Log worker pickup — this is the first SSE-visible event from the worker
    await _safe_log("INFO", "Worker picked up analysis job")
    await _safe_log("INFO", f"Worker directory: {os.getcwd()}, temp: {temp_dir}")

    try:
        # Get repository
        repo = await repo_service.get_repository(repository_id)
        if not repo:
            raise ValueError(f"Repository {repository_id} not found")

        # Clone repository
        await _safe_log("INFO", f"Cloning {repo.full_name}...")
        repo_path = await repo_service.clone_repository(repo, token, temp_dir)
        repo_path = Path(repo_path).resolve()
        await _safe_log("INFO", f"Repository cloned to: {repo_path}")

        # Verify the clone before proceeding
        if not repo_path.exists():
            raise RuntimeError(f"Repository path does not exist after clone: {repo_path}")
        if not repo_path.is_dir():
            raise RuntimeError(f"Repository path is not a directory: {repo_path}")

        items = await asyncio.to_thread(lambda: list(repo_path.iterdir()))
        await _safe_log("INFO", f"Repository has {len(items)} items")

        # Run analysis
        print("analyze_repository: Running analysis pipeline")
        await analysis_service.run_analysis(
            analysis_id=analysis_id,
            repo_path=repo_path,
            token=token,
            prompt_config=prompt_config,
        )
        print("analyze_repository: Analysis complete")
    except asyncio.CancelledError:
        # ARQ job timeout sends CancelledError which bypasses `except Exception`
        error_msg = "Analysis cancelled (job timeout exceeded)"
        print(f"analyze_repository: {error_msg}")
        await _safe_log("ERROR", error_msg)
        await _mark_failed(error_msg)
        raise
    except Exception as e:
        error_msg = str(e)
        print(f"analyze_repository: Error: {error_msg}")
        import traceback
        traceback.print_exc()

        # Log the error to the SSE stream so the UI shows it
        await _safe_log("ERROR", f"Worker error: {error_msg}")

        # Robustly mark analysis as failed (with retry)
        await _mark_failed(error_msg)
        raise
    finally:
        print("analyze_repository: Cleaning up temporary files")
        try:
            await repo_service.cleanup_temp_repository(temp_dir)
        except Exception as cleanup_error:
            print(f"analyze_repository: Cleanup error: {cleanup_error}")


try:
    _worker_settings = get_settings()
    _redis_url = _worker_settings.redis_url
    _job_timeout = _worker_settings.analysis_timeout_seconds
except Exception:
    # Fallback so tests that import functions from this module don't crash
    # when Settings validation fails (e.g. missing env vars in test env).
    _redis_url = "redis://localhost:6379"
    _job_timeout = 3600


class WorkerSettings:
    """ARQ worker settings."""
    redis_settings = RedisSettings.from_dsn(_redis_url)
    redis_settings.conn_timeout = 10  # Analysis blocks event loop; 1s default causes reconnect failures
    redis_settings.retry_on_timeout = True
    functions = [analyze_repository]
    on_startup = startup
    on_shutdown = shutdown
    job_timeout = _job_timeout
