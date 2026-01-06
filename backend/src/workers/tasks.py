"""Background task definitions."""
from arq.connections import RedisSettings
from pathlib import Path
from application.services.analysis_service import AnalysisService
from application.services.repository_service import RepositoryService
from config.settings import get_settings
from config.container import Container
from infrastructure.persistence.user_repository import SupabaseUserRepository
from infrastructure.persistence.repository_repository import SupabaseRepositoryRepository
from infrastructure.persistence.analysis_repository import SupabaseAnalysisRepository
from infrastructure.persistence.analysis_event_repository import SupabaseAnalysisEventRepository
from infrastructure.analysis.structure_analyzer import StructureAnalyzer
from infrastructure.storage.temp_storage import TempStorage
from application.services.phased_blueprint_generator import PhasedBlueprintGenerator


async def startup(ctx):
    """Worker startup hook."""
    print("Worker startup: Initializing container...")
    container = Container()
    # Initialize async resources
    await container.init_resources()
    print("Worker startup: Resources initialized")
    
    # CRITICAL: Resolve supabase_client Resource first
    supabase_client = await container.supabase_client()
    print(f"Worker startup: Supabase client resolved: {type(supabase_client)}")
    
    # Manually create repositories with resolved client
    user_repo = SupabaseUserRepository(client=supabase_client)
    repo_repo = SupabaseRepositoryRepository(client=supabase_client)
    analysis_repo = SupabaseAnalysisRepository(client=supabase_client)
    event_repo = SupabaseAnalysisEventRepository(client=supabase_client)
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
    
    # Pass supabase_client to enable RAG-based retrieval
    phased_blueprint_generator = PhasedBlueprintGenerator(
        settings=settings,
        supabase_client=supabase_client,  # Enable RAG for full codebase analysis
    )
    
    print(f"Worker startup: Analysis infrastructure initialized with RAG enabled")
    
    analysis_service = AnalysisService(
        analysis_repo=analysis_repo,
        repository_repo=repo_repo,
        event_repo=event_repo,
        structure_analyzer=structure_analyzer,
        persistent_storage=storage,
        phased_blueprint_generator=phased_blueprint_generator,
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
    print(f"analyze_repository: Starting analysis {analysis_id} for repository {repository_id}")
    
    # Get services from context
    analysis_service = ctx.get("analysis_service")
    repo_service = ctx.get("repository_service")
    container = ctx.get("container")
    
    print(f"analyze_repository: repo_service type: {type(repo_service)}")
    
    if not repo_service:
        raise ValueError("repository_service not found in context")
    if not analysis_service:
        raise ValueError("analysis_service not found in context")
    
    # Verify it's not a Future (check if it's a coroutine/Future)
    import asyncio
    if asyncio.iscoroutine(repo_service) or isinstance(repo_service, asyncio.Future):
        raise ValueError(f"repository_service is a Future/coroutine, not a service: {type(repo_service)}")
    
    # Get analysis repository to update status on errors
    supabase_client = await container.supabase_client()
    analysis_repo = SupabaseAnalysisRepository(client=supabase_client)
    
    # Use temporary storage for cloning
    temp_storage = TempStorage()
    temp_dir = temp_storage.get_base_path()
    
    try:
        # Get repository
        print(f"analyze_repository: Getting repository {repository_id}")
        repo = await repo_service.get_repository(repository_id)
        if not repo:
            raise ValueError(f"Repository {repository_id} not found")
        
        print(f"analyze_repository: Repository found: {repo.full_name}")
        
        # Clone repository
        print(f"analyze_repository: Cloning repository to {temp_dir}")
        repo_path = await repo_service.clone_repository(repo, token, temp_dir)
        print(f"analyze_repository: Repository cloned to {repo_path}")
        
        # Run analysis (this will handle its own errors and mark analysis as failed)
        print(f"analyze_repository: Running analysis pipeline")
        await analysis_service.run_analysis(
            analysis_id=analysis_id,
            repo_path=repo_path,
            token=token,
            prompt_config=prompt_config,
        )
        print(f"analyze_repository: Analysis complete")
    except Exception as e:
        # Ensure analysis is marked as failed if error occurs outside run_analysis
        print(f"analyze_repository: Error occurred: {str(e)}")
        import traceback
        traceback.print_exc()
        
        try:
            analysis = await analysis_repo.get_by_id(analysis_id)
            if analysis and analysis.status != "failed":
                analysis.fail(str(e))
                await analysis_repo.update(analysis)
        except Exception as update_error:
            print(f"analyze_repository: Failed to update analysis status: {str(update_error)}")
        
        raise
    finally:
        # Cleanup
        print(f"analyze_repository: Cleaning up temporary files")
        try:
            await repo_service.cleanup_temp_repository(temp_dir)
        except Exception as cleanup_error:
            print(f"analyze_repository: Cleanup error: {str(cleanup_error)}")


class WorkerSettings:
    """ARQ worker settings."""
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    functions = [analyze_repository]
    on_startup = startup
    on_shutdown = shutdown
