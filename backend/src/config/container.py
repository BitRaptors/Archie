"""Dependency injection container."""
from dependency_injector import containers, providers
from arq import create_pool
from arq.connections import RedisSettings
from config.settings import get_settings

from infrastructure.persistence.db_factory import create_db, shutdown_db
from infrastructure.persistence.repository_repository import RepositoryRepository
from infrastructure.persistence.analysis_repository import AnalysisRepository
from infrastructure.persistence.analysis_event_repository import AnalysisEventRepository
from infrastructure.persistence.user_repository import UserRepository
from infrastructure.persistence.prompt_repository import PromptRepository
from infrastructure.persistence.prompt_revision_repository import PromptRevisionRepository
from application.services.github_service import GitHubService
from application.services.repository_service import RepositoryService
from application.services.analysis_service import AnalysisService
from application.services.delivery_service import DeliveryService
from application.services.intent_layer_service import IntentLayerService
from application.services.prompt_service import PromptService
from infrastructure.prompts.database_prompt_loader import DatabasePromptLoader
from infrastructure.storage.local_storage import LocalStorage


async def _init_and_return_db():
    """Resource initializer: create the DB client, return it. Shutdown closes pool."""
    db = await create_db()
    return db


async def _shutdown_db_resource(db):
    """Resource shutdown hook — called by container.shutdown_resources()."""
    await shutdown_db()


class Container(containers.DeclarativeContainer):
    """Application dependency injection container."""

    # Configuration
    config = providers.Configuration()
    settings = providers.Singleton(get_settings)

    # Database — backend-agnostic (Supabase or local Postgres)
    db = providers.Resource(
        _init_and_return_db,
    )

    # ARQ Pool - Using a Resource for async initialization (optional, returns None if Redis unavailable)
    @staticmethod
    async def _create_arq_pool(redis_url: str):
        try:
            settings = RedisSettings.from_dsn(redis_url)
            settings.conn_timeout = 2  # Fast fail if Redis is not running
            settings.conn_retries = 1
            pool = await create_pool(settings)
            return pool
        except Exception as e:
            print(f"Warning: Redis/ARQ unavailable ({e}). Analysis will run in-process.")
            return None

    arq_pool = providers.Resource(
        _create_arq_pool,
        redis_url=settings.provided.redis_url,
    )

    # Storage
    storage = providers.Singleton(
        LocalStorage,
        base_path=settings.provided.storage_path,
    )

    # Repositories -- using the DB abstraction
    user_repository = providers.Factory(
        UserRepository,
        db=db,
    )
    repository_repository = providers.Factory(
        RepositoryRepository,
        db=db,
    )
    analysis_repository = providers.Factory(
        AnalysisRepository,
        db=db,
    )
    analysis_event_repository = providers.Factory(
        AnalysisEventRepository,
        db=db,
    )
    prompt_repository = providers.Factory(
        PromptRepository,
        db=db,
    )
    prompt_revision_repository = providers.Factory(
        PromptRevisionRepository,
        db=db,
    )

    # Prompt infrastructure
    database_prompt_loader = providers.Singleton(
        DatabasePromptLoader,
        prompt_repo=prompt_repository,
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

    intent_layer_service = providers.Singleton(
        IntentLayerService,
        storage=storage,
        settings=settings,
        db_client=db,
    )

    analysis_service = providers.Singleton(
        AnalysisService,
        analysis_repo=analysis_repository,
        repository_repo=repository_repository,
        event_repo=analysis_event_repository,
        structure_analyzer=structure_analyzer,
        persistent_storage=storage,
        phased_blueprint_generator=phased_blueprint_generator,
        intent_layer_service=intent_layer_service,
    )

    delivery_service = providers.Singleton(
        DeliveryService,
        storage=storage,
        intent_layer_service=intent_layer_service,
    )

    prompt_service = providers.Singleton(
        PromptService,
        prompt_repo=prompt_repository,
        revision_repo=prompt_revision_repository,
        prompt_loader=database_prompt_loader,
    )
