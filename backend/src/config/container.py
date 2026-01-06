"""Dependency injection container."""
from dependency_injector import containers, providers
from supabase import create_async_client, Client
import redis.asyncio as redis
from arq import create_pool
from arq.connections import RedisSettings
from config.settings import get_settings

from infrastructure.persistence.repository_repository import SupabaseRepositoryRepository
from infrastructure.persistence.analysis_repository import SupabaseAnalysisRepository
from infrastructure.persistence.analysis_event_repository import SupabaseAnalysisEventRepository
from infrastructure.persistence.user_repository import SupabaseUserRepository
from application.services.github_service import GitHubService
from application.services.repository_service import RepositoryService
from application.services.analysis_service import AnalysisService
from infrastructure.storage.local_storage import LocalStorage


class Container(containers.DeclarativeContainer):
    """Application dependency injection container."""

    # Configuration
    config = providers.Configuration()
    settings = providers.Singleton(get_settings)

    # Redis
    redis_client = providers.Singleton(
        redis.from_url,
        url=settings.provided.redis_url,
    )

    # Supabase (Database) - Using Resource for async initialization
    @staticmethod
    async def _create_supabase_client(supabase_url: str, supabase_key: str):
        return await create_async_client(supabase_url, supabase_key)

    supabase_client = providers.Resource(
        _create_supabase_client,
        supabase_url=settings.provided.supabase_url,
        supabase_key=settings.provided.supabase_key,
    )

    # ARQ Pool - Using a Resource for async initialization
    @staticmethod
    async def _create_arq_pool(redis_url: str):
        return await create_pool(RedisSettings.from_dsn(redis_url))

    arq_pool = providers.Resource(
        _create_arq_pool,
        redis_url=settings.provided.redis_url,
    )

    # Storage
    storage = providers.Singleton(
        LocalStorage,
        base_path=settings.provided.storage_path,
    )

    # Repositories - Using Factory so they're created after supabase_client is resolved
    # We'll ensure supabase_client is initialized before accessing these
    user_repository = providers.Factory(
        SupabaseUserRepository,
        client=supabase_client,
    )
    repository_repository = providers.Factory(
        SupabaseRepositoryRepository,
        client=supabase_client,
    )
    analysis_repository = providers.Factory(
        SupabaseAnalysisRepository,
        client=supabase_client,
    )
    analysis_event_repository = providers.Factory(
        SupabaseAnalysisEventRepository,
        client=supabase_client,
    )

    # Services
    github_service = providers.Singleton(GitHubService)
    
    repository_service = providers.Singleton(
        RepositoryService,
        repository_repo=repository_repository,
        github_service=github_service,
        storage=storage,
    )
    
    # Analysis infrastructure - only what's needed
    structure_analyzer = providers.Singleton(object)
    
    # Phased blueprint generator
    phased_blueprint_generator = providers.Singleton(
        lambda: None  # Will be initialized in worker with actual Settings
    )

    analysis_service = providers.Singleton(
        AnalysisService,
        analysis_repo=analysis_repository,
        repository_repo=repository_repository,
        event_repo=analysis_event_repository,
        structure_analyzer=structure_analyzer,
        persistent_storage=storage,
        phased_blueprint_generator=phased_blueprint_generator,
    )
