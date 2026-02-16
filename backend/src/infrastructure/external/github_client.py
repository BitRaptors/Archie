"""GitHub API client."""
from typing import Any
from github import Github
from github.GithubException import GithubException
from domain.exceptions.domain_exceptions import ValidationError, AuthorizationError


class GitHubClient:
    """GitHub API client wrapper."""

    def __init__(self, token: str):
        """Initialize GitHub client with token."""
        self._client = Github(token)
        self._token = token

    def validate_token(self) -> bool:
        """Validate GitHub token by attempting to get authenticated user."""
        try:
            user = self._client.get_user()
            return user is not None
        except GithubException:
            return False

    def get_user(self) -> dict[str, Any]:
        """Get authenticated user information."""
        try:
            user = self._client.get_user()
            return {
                "login": user.login,
                "id": user.id,
                "name": user.name,
                "email": user.email,
                "avatar_url": user.avatar_url,
            }
        except GithubException as e:
            if e.status == 401:
                raise AuthorizationError("Invalid GitHub token")
            raise ValidationError(f"Failed to get user: {str(e)}")

    def list_repositories(self, limit: int = 100) -> list[dict[str, Any]]:
        """List user's repositories."""
        try:
            repos = self._client.get_user().get_repos()
            result = []
            for repo in repos[:limit]:
                result.append({
                    "id": str(repo.id),
                    "name": repo.name,
                    "full_name": repo.full_name,
                    "owner": repo.owner.login,
                    "url": repo.html_url,
                    "description": repo.description,
                    "language": repo.language,
                    "default_branch": repo.default_branch,
                    "private": repo.private,
                    "fork": repo.fork,
                    "created_at": repo.created_at.isoformat() if repo.created_at else None,
                    "updated_at": repo.updated_at.isoformat() if repo.updated_at else None,
                })
            return result
        except GithubException as e:
            if e.status == 401:
                raise AuthorizationError("Invalid GitHub token")
            raise ValidationError(f"Failed to list repositories: {str(e)}")

    def get_repository(self, owner: str, name: str) -> dict[str, Any]:
        """Get repository details."""
        try:
            repo = self._client.get_repo(f"{owner}/{name}")
            return {
                "id": str(repo.id),
                "name": repo.name,
                "full_name": repo.full_name,
                "owner": repo.owner.login,
                "url": repo.html_url,
                "description": repo.description,
                "language": repo.language,
                "default_branch": repo.default_branch,
                "private": repo.private,
                "fork": repo.fork,
                "created_at": repo.created_at.isoformat() if repo.created_at else None,
                "updated_at": repo.updated_at.isoformat() if repo.updated_at else None,
            }
        except GithubException as e:
            if e.status == 404:
                raise ValidationError(f"Repository {owner}/{name} not found")
            if e.status == 401:
                raise AuthorizationError("Invalid GitHub token")
            raise ValidationError(f"Failed to get repository: {str(e)}")

