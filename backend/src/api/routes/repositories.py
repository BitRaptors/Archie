"""Repository routes."""
from fastapi import APIRouter, HTTPException, Header, Request
from typing import List, Optional
from api.dto.requests import CreateRepositoryRequest, StartAnalysisRequest
from api.dto.responses import RepositoryResponse, AnalysisResponse
from application.services.github_service import GitHubService

router = APIRouter(prefix="/repositories", tags=["repositories"])


def get_token_from_header(request: Request) -> Optional[str]:
    """Extract Bearer token from Authorization header."""
    authorization = request.headers.get("Authorization", "")
    if authorization and authorization.startswith("Bearer "):
        return authorization.replace("Bearer ", "")
    return None


@router.get("/", response_model=List[RepositoryResponse])
async def list_repositories(
    request: Request,
    limit: int = 100,
    offset: int = 0,
):
    """List user's repositories."""
    # Extract token from Authorization header
    token = get_token_from_header(request)
    
    if not token:
        return []
    
    # Get github service from container
    container = request.app.container
    github_service = container.github_service()
    
    try:
        # Debug: log first and last 4 chars of token
        if token:
            print(f"DEBUG: Token received: {token[:4]}...{token[-4:]} (length: {len(token)})")
        else:
            print("DEBUG: No token received")
        repos = await github_service.list_repositories(token, limit=limit)
        return repos
    except Exception as e:
        import traceback
        print(f"Error listing repositories: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/", response_model=RepositoryResponse)
async def create_repository(
    request: CreateRepositoryRequest,
    user_id: str,  # Would come from auth
    token: str,  # Would come from auth
):
    """Create repository from GitHub."""
    # TODO: Implement with proper service injection
    raise HTTPException(status_code=501, detail="Not implemented")


@router.get("/{repo_id}", response_model=RepositoryResponse)
async def get_repository(repo_id: str):
    """Get repository details."""
    # TODO: Implement with proper service injection
    raise HTTPException(status_code=501, detail="Not implemented")


@router.post("/{owner}/{repo}/analyze", response_model=AnalysisResponse)
async def start_analysis(
    owner: str,
    repo: str,
    request: Request,
    analysis_request: StartAnalysisRequest | None = None,
):
    """Start analysis for a repository."""
    # Extract token
    token = get_token_from_header(request)
    if not token:
        raise HTTPException(status_code=401, detail="Missing GitHub token")

    # Get container
    container = request.app.container
    
    # CRITICAL: Resolve supabase_client Resource first to ensure it's initialized
    supabase_client = await container.supabase_client()
    
    # Manually create repositories with resolved client to avoid Future issues
    from infrastructure.persistence.user_repository import SupabaseUserRepository
    from infrastructure.persistence.repository_repository import SupabaseRepositoryRepository
    from infrastructure.persistence.analysis_repository import SupabaseAnalysisRepository
    from infrastructure.persistence.analysis_event_repository import SupabaseAnalysisEventRepository
    
    user_repo = SupabaseUserRepository(client=supabase_client)
    repo_repo = SupabaseRepositoryRepository(client=supabase_client)
    analysis_repo = SupabaseAnalysisRepository(client=supabase_client)
    event_repo = SupabaseAnalysisEventRepository(client=supabase_client)
    
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
    
    # Pass supabase_client to enable RAG-based retrieval
    phased_blueprint_generator = PhasedBlueprintGenerator(
        settings=settings,
        supabase_client=supabase_client,  # Enable RAG for full codebase analysis
    )
    
    # Create analysis service
    analysis_service = AnalysisService(
        analysis_repo=analysis_repo,
        repository_repo=repo_repo,
        event_repo=event_repo,
        structure_analyzer=structure_analyzer,
        persistent_storage=storage,
        phased_blueprint_generator=phased_blueprint_generator,
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
        
        # 3. Enqueue background task
        try:
            arq_pool = await container.arq_pool()
            await arq_pool.enqueue_job(
                "analyze_repository",
                analysis_id=analysis.id,
                repository_id=repository.id,
                token=token,
                prompt_config=prompt_config,
            )
        except Exception as queue_err:
            # Still return the analysis record, but it will stay in pending
            # Or fail it immediately
            analysis.fail(f"Failed to queue: {str(queue_err)}")
            await analysis_repo.update(analysis)
            raise HTTPException(status_code=500, detail=f"Task queue error: {str(queue_err)}")
        
        return analysis
    except Exception as e:
        import traceback
        print(f"Error in start_analysis: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{repo_id}/status", response_model=AnalysisResponse)
async def get_analysis_status(repo_id: str):
    """Get analysis status for repository."""
    # TODO: Implement with proper service injection
    raise HTTPException(status_code=501, detail="Not implemented")


@router.get("/{repo_id}/blueprint")
async def get_blueprint(repo_id: str):
    """Get generated blueprint."""
    # TODO: Implement with proper service injection
    raise HTTPException(status_code=501, detail="Not implemented")
