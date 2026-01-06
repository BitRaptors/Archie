"""Background task definitions."""
from arq.connections import RedisSettings
from pathlib import Path
from application.services.analysis_service import AnalysisService
from application.services.repository_service import RepositoryService
from infrastructure.storage.temp_storage import TempStorage
from infrastructure.storage.local_storage import LocalStorage
from config.settings import get_settings
from config.container import Container
from infrastructure.persistence.user_repository import SupabaseUserRepository
from infrastructure.persistence.repository_repository import SupabaseRepositoryRepository
from infrastructure.persistence.analysis_repository import SupabaseAnalysisRepository
from infrastructure.persistence.analysis_event_repository import SupabaseAnalysisEventRepository
from infrastructure.analysis.structure_analyzer import StructureAnalyzer
from infrastructure.analysis.ast_extractor import ASTExtractor
from infrastructure.analysis.embedding_generator import EmbeddingGenerator
from infrastructure.analysis.pattern_detector import PatternDetector
from infrastructure.analysis.semantic_pattern_finder import SemanticPatternFinder
from infrastructure.analysis.query_embedder import QueryEmbedder
from infrastructure.analysis.vector_store import PgVectorStore
from infrastructure.ai.blueprint_analyzer import BlueprintAnalyzer
from application.services.blueprint_generator import BlueprintGenerator
from application.services.prompt_service import PromptService
from domain.entities.analysis_prompt import AnalysisPrompt
from domain.interfaces.repositories import IRepository


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
    
    # Initialize analysis infrastructure components
    # 1. Simple analyzers (no dependencies)
    structure_analyzer = StructureAnalyzer()
    ast_extractor = ASTExtractor()
    query_embedder = QueryEmbedder()
    
    # 2. Vector store (needs supabase_client)
    vector_store = PgVectorStore(supabase_client)
    
    # 3. Embedding generator (needs vector_store)
    embedding_generator = EmbeddingGenerator(vector_store)
    
    # 4. Semantic pattern finder (needs vector_store and query_embedder)
    semantic_pattern_finder = SemanticPatternFinder(vector_store, query_embedder)
    
    # 5. Pattern detector (needs semantic_pattern_finder)
    pattern_detector = PatternDetector(semantic_pattern_finder)
    
    # 6. Prompt service (needs a prompt repository - create a simple mock for now)
    # TODO: Create proper prompt repository implementation
    class MockPromptRepository(IRepository[AnalysisPrompt, str]):
        async def get_by_id(self, id: str) -> AnalysisPrompt | None:
            return None
        async def add(self, entity: AnalysisPrompt) -> AnalysisPrompt:
            return entity
        async def update(self, entity: AnalysisPrompt) -> AnalysisPrompt:
            return entity
        async def delete(self, id: str) -> None:
            pass
        async def get_all(self, limit: int = 100, offset: int = 0) -> list[AnalysisPrompt]:
            return []
    
    prompt_repo = MockPromptRepository()
    prompt_service = PromptService(prompt_repo)
    
    # 7. Blueprint analyzer (needs prompt_service)
    blueprint_analyzer = BlueprintAnalyzer(prompt_service)
    
    # 8. Blueprint generator (needs prompt_service and blueprint_analyzer)
    blueprint_generator = BlueprintGenerator(prompt_service, blueprint_analyzer)
    
    # 9. Temp storage
    temp_storage = TempStorage()
    
    print(f"Worker startup: Analysis infrastructure initialized")
    
    analysis_service = AnalysisService(
        analysis_repo=analysis_repo,
        repository_repo=repo_repo,
        event_repo=event_repo,
        structure_analyzer=structure_analyzer,
        embedding_generator=embedding_generator,
        ast_extractor=ast_extractor,
        pattern_detector=pattern_detector,
        semantic_pattern_finder=semantic_pattern_finder,
        blueprint_analyzer=blueprint_analyzer,
        blueprint_generator=blueprint_generator,
        prompt_service=prompt_service,
        temp_storage=temp_storage,
        persistent_storage=storage,
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
