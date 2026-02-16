"""GitHub service."""
from typing import Any
from infrastructure.external.github_client import GitHubClient
from domain.exceptions.domain_exceptions import ValidationError, AuthorizationError


class GitHubService:
    """Service for GitHub operations."""

    def __init__(self):
        """Initialize GitHub service."""
        pass

    def create_client(self, token: str) -> GitHubClient:
        """Create GitHub client with token."""
        return GitHubClient(token)

    async def validate_token(self, token: str) -> bool:
        """Validate GitHub token."""
        client = self.create_client(token)
        return client.validate_token()

    async def get_user(self, token: str) -> dict[str, Any]:
        """Get authenticated user information."""
        client = self.create_client(token)
        return client.get_user()

    async def list_repositories(self, token: str, limit: int = 100) -> list[dict[str, Any]]:
        """List user's repositories."""
        client = self.create_client(token)
        return client.list_repositories(limit=limit)

    async def get_repository(self, token: str, owner: str, name: str) -> dict[str, Any]:
        """Get repository details."""
        client = self.create_client(token)
        return client.get_repository(owner, name)


