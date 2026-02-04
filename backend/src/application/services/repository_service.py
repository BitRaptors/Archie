"""Repository service."""
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import Any
from domain.entities.repository import Repository
from domain.interfaces.repositories import IRepository
from domain.exceptions.domain_exceptions import NotFoundError, ConflictError
from application.services.github_service import GitHubService
from infrastructure.storage.storage_interface import IStorage


class RepositoryService:
    """Service for repository operations."""

    def __init__(
        self,
        repository_repo: IRepository[Repository, str],
        github_service: GitHubService,
        storage: IStorage,
    ):
        """Initialize repository service."""
        self._repo = repository_repo
        self._github = github_service
        self._storage = storage

    async def create_repository(
        self,
        user_id: str,
        token: str,
        owner: str,
        name: str,
    ) -> Repository:
        """Create repository from GitHub."""
        # Check if already exists
        existing = await self._repo.get_by_full_name(user_id, owner, name)
        if existing:
            raise ConflictError("Repository", "full_name", f"{owner}/{name}")

        # Get repository details from GitHub
        github_repo = await self._github.get_repository(token, owner, name)

        # Create repository entity
        repo = Repository.create(
            user_id=user_id,
            owner=github_repo["owner"],
            name=github_repo["name"],
            full_name=github_repo["full_name"],
            url=github_repo["url"],
            description=github_repo.get("description"),
            language=github_repo.get("language"),
            default_branch=github_repo.get("default_branch", "main"),
        )

        return await self._repo.add(repo)

    async def get_repository(self, repo_id: str) -> Repository:
        """Get repository by ID."""
        repo = await self._repo.get_by_id(repo_id)
        if not repo:
            raise NotFoundError("Repository", repo_id)
        return repo

    async def get_repository_by_full_name(self, user_id: str, owner: str, name: str) -> Repository | None:
        """Get repository by full name."""
        return await self._repo.get_by_full_name(user_id, owner, name)

    async def list_user_repositories(self, user_id: str, limit: int = 100, offset: int = 0) -> list[Repository]:
        """List user's repositories."""
        return await self._repo.get_by_user_id(user_id, limit=limit, offset=offset)

    async def clone_repository(self, repo: Repository, token: str, temp_dir: Path) -> Path:
        """Clone repository to temporary directory."""
        repo_path = temp_dir / repo.full_name.replace("/", "_")
        
        # Clean up if already exists
        if repo_path.exists():
            shutil.rmtree(repo_path)
        
        # Ensure temp_dir exists
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        # Clone with token authentication
        clone_url = f"https://{token}@github.com/{repo.full_name}.git"
        result = subprocess.run(
            ["git", "clone", "--depth", "1", clone_url, str(repo_path)],
            check=True,
            capture_output=True,
            text=True,
        )
        
        # Verify clone succeeded - check if directory exists and has content
        if not repo_path.exists():
            raise RuntimeError(f"Repository clone failed: directory {repo_path} does not exist after clone")
        
        if not repo_path.is_dir():
            raise RuntimeError(f"Repository clone failed: {repo_path} is not a directory")
        
        # Check if repository has any content (at least .git should be there)
        items = list(repo_path.iterdir())
        if len(items) == 0:
            raise RuntimeError(f"Repository clone failed: directory {repo_path} is empty after clone")
        
        # Resolve to absolute path to avoid any path resolution issues
        repo_path = repo_path.resolve()
        
        return repo_path

    async def cleanup_temp_repository(self, repo_path: Path) -> None:
        """Clean up temporary repository directory."""
        if repo_path.exists():
            shutil.rmtree(repo_path)

