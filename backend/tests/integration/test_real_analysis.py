import sys
from pathlib import Path
import pytest
import os
import uuid
from dotenv import load_dotenv
from unittest.mock import MagicMock

# Add src to path
src_path = str(Path(__file__).parent.parent.parent / "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

# Load environment variables
load_dotenv(Path(__file__).parent.parent.parent / ".env.local")

from config.container import Container
from config.settings import get_settings
from application.services.repository_service import RepositoryService
from application.services.analysis_service import AnalysisService
from domain.entities.user import User
from infrastructure.persistence.user_repository import SupabaseUserRepository
from infrastructure.persistence.repository_repository import SupabaseRepositoryRepository
from infrastructure.persistence.analysis_repository import SupabaseAnalysisRepository
from infrastructure.persistence.analysis_event_repository import SupabaseAnalysisEventRepository
from infrastructure.storage.local_storage import LocalStorage
from application.services.phased_blueprint_generator import PhasedBlueprintGenerator
from infrastructure.analysis.structure_analyzer import StructureAnalyzer


@pytest.fixture
def anyio_backend():
    return 'asyncio'


@pytest.fixture
async def container():
    """Create and initialize container with real dependencies."""
    container = Container()
    await container.init_resources()
    yield container
    await container.shutdown_resources()


@pytest.fixture
async def github_token():
    """Get GitHub token from environment."""
    token = os.getenv("GITHUB_TOKEN") or os.getenv("github_token")
    if not token:
        pytest.skip("GITHUB_TOKEN not found in environment")
    return token


@pytest.mark.anyio
async def test_analyze_bitraptors_raptamagochi(container, github_token):
    """Test analyzing the actual BitRaptors/raptamagochi repository."""
    # Use a fixed UUID for the default user (or generate a new one)
    user_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, "default-user"))
    owner = "BitRaptors"
    repo_name = "raptamagochi"
    
    # CRITICAL: Resolve supabase_client Resource first
    supabase_client = await container.supabase_client()
    print(f"Supabase client initialized: {type(supabase_client)}")
    
    # Now create repositories with the resolved client
    user_repo = SupabaseUserRepository(client=supabase_client)
    repo_repo = SupabaseRepositoryRepository(client=supabase_client)
    analysis_repo = SupabaseAnalysisRepository(client=supabase_client)
    event_repo = SupabaseAnalysisEventRepository(client=supabase_client)
    
    print(f"User repo type: {type(user_repo)}")
    print(f"User repo client type: {type(user_repo._client)}")
    
    # Create services with resolved repositories
    storage = container.storage()
    github_service = container.github_service()
    
    repo_service = RepositoryService(
        repository_repo=repo_repo,
        github_service=github_service,
        storage=storage,
    )
    
    # Create mock dependencies for AnalysisService
    structure_analyzer = StructureAnalyzer()
    
    # Create mock phased blueprint generator
    mock_generator = MagicMock(spec=PhasedBlueprintGenerator)
    mock_generator._progress_callback = None
    
    analysis_service = AnalysisService(
        analysis_repo=analysis_repo,
        repository_repo=repo_repo,
        event_repo=event_repo,
        structure_analyzer=structure_analyzer,
        persistent_storage=storage,
        phased_blueprint_generator=mock_generator,
    )
    
    # Ensure user exists
    user = await user_repo.get_by_id(user_id)
    if not user:
        user = User.create(github_token_encrypted="dummy_encrypted_token")
        user.id = user_id
        user = await user_repo.add(user)
        print(f"Created user: {user.id}")
    else:
        print(f"Found existing user: {user.id}")
    
    # Get or create repository
    repository = await repo_service.get_repository_by_full_name(user_id, owner, repo_name)
    if not repository:
        print(f"Creating repository record for {owner}/{repo_name}")
        repository = await repo_service.create_repository(user_id, github_token, owner, repo_name)
        print(f"Created repository: {repository.id}")
    else:
        print(f"Found existing repository: {repository.id}")
    
    # Start analysis
    print(f"Starting analysis for {repository.id}")
    analysis = await analysis_service.start_analysis(repository.id, None)
    print(f"Created analysis: {analysis.id}, status: {analysis.status}")
    
    # Try to enqueue job
    try:
        arq_pool = await container.arq_pool()
        print(f"Got ARQ pool: {type(arq_pool)}")
        
        job = await arq_pool.enqueue_job(
            "analyze_repository",
            analysis_id=analysis.id,
            repository_id=repository.id,
            token=github_token,
            prompt_config=None,
        )
        print(f"Enqueued job: {job.job_id}")
        assert job is not None
        print("✅ Test passed! Analysis job enqueued successfully.")
    except Exception as e:
        print(f"Failed to enqueue job: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        raise


@pytest.mark.anyio
async def test_repository_service_get_or_create(container, github_token):
    """Test repository service operations."""
    user_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, "default-user"))
    owner = "BitRaptors"
    repo_name = "raptamagochi"
    
    # Ensure supabase client is initialized
    supabase_client = await container.supabase_client()
    repo_repo = SupabaseRepositoryRepository(client=supabase_client)
    
    storage = container.storage()
    github_service = container.github_service()
    
    repo_service = RepositoryService(
        repository_repo=repo_repo,
        github_service=github_service,
        storage=storage,
    )
    
    # Test get by full name
    repo = await repo_service.get_repository_by_full_name(user_id, owner, repo_name)
    if repo:
        print(f"Found repository: {repo.id}, {repo.full_name}")
    else:
        print(f"Repository not found, creating...")
        repo = await repo_service.create_repository(user_id, github_token, owner, repo_name)
        print(f"Created: {repo.id}, {repo.full_name}")
    
    assert repo is not None
    assert repo.owner == owner
    assert repo.name == repo_name


@pytest.mark.anyio
async def test_github_service_list_repos(container, github_token):
    """Test GitHub service can list repositories."""
    github_service = container.github_service()
    
    repos = await github_service.list_repositories(github_token, limit=10)
    print(f"Found {len(repos)} repositories")
    
    # Check if raptamagochi is in the list
    raptamagochi = next((r for r in repos if r["name"] == "raptamagochi"), None)
    if raptamagochi:
        print(f"Found raptamagochi: {raptamagochi['full_name']}")
    else:
        print("raptamagochi not found in repository list")
        # Print first few repo names for debugging
        print(f"First 5 repos: {[r['name'] for r in repos[:5]]}")
    
    assert len(repos) > 0
