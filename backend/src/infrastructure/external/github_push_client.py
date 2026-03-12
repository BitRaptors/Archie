"""GitHub push client for write operations (branch, commit, PR)."""
import base64
from typing import Any

from github import Github, InputGitTreeElement
from github.GithubException import GithubException, UnknownObjectException

from domain.exceptions.domain_exceptions import ValidationError, AuthorizationError


class GitHubPushClient:
    """GitHub API client for write operations: branches, commits, pull requests."""

    def __init__(self, token: str):
        self._client = Github(token)

    def get_default_branch(self, repo_full_name: str) -> str:
        """Get the default branch name for a repository."""
        try:
            repo = self._client.get_repo(repo_full_name)
            return repo.default_branch
        except GithubException as e:
            if e.status == 401:
                raise AuthorizationError("Invalid GitHub token")
            if e.status == 404:
                raise ValidationError(f"Repository {repo_full_name} not found")
            raise ValidationError(f"Failed to get default branch: {e}")

    def get_file_content(self, repo_full_name: str, path: str, ref: str) -> str | None:
        """Read a file from the repo. Returns None if file doesn't exist."""
        try:
            repo = self._client.get_repo(repo_full_name)
            contents = repo.get_contents(path, ref=ref)
            return base64.b64decode(contents.content).decode("utf-8")
        except (GithubException, UnknownObjectException) as e:
            if hasattr(e, "status") and e.status == 404:
                return None
            if hasattr(e, "status") and e.status == 401:
                raise AuthorizationError("Invalid GitHub token")
            raise ValidationError(f"Failed to read file {path}: {e}")

    def create_branch(
        self, repo_full_name: str, branch_name: str, base_branch: str, *, force: bool = False
    ) -> str:
        """Create a new branch from a base branch. Returns the new branch ref.

        If force=True and the branch already exists, it is reset to the
        current tip of base_branch so the next commit starts fresh.
        """
        try:
            repo = self._client.get_repo(repo_full_name)
            base_ref = repo.get_git_ref(f"heads/{base_branch}")
            base_sha = base_ref.object.sha
            repo.create_git_ref(ref=f"refs/heads/{branch_name}", sha=base_sha)
            return f"refs/heads/{branch_name}"
        except GithubException as e:
            if e.status == 401:
                raise AuthorizationError("Invalid GitHub token")
            if e.status == 422 and force:
                # Branch already exists — reset it to base branch tip
                existing_ref = repo.get_git_ref(f"heads/{branch_name}")
                existing_ref.edit(sha=base_sha, force=True)
                return f"refs/heads/{branch_name}"
            if e.status == 422:
                raise ValidationError(f"Branch '{branch_name}' already exists")
            raise ValidationError(f"Failed to create branch: {e}")

    def commit_files(
        self,
        repo_full_name: str,
        branch_name: str,
        files: dict[str, str],
        commit_message: str,
        executable_paths: set[str] | None = None,
    ) -> str:
        """Commit multiple files atomically using the Git Trees API. Returns commit SHA."""
        executable_paths = executable_paths or set()
        try:
            repo = self._client.get_repo(repo_full_name)
            ref = repo.get_git_ref(f"heads/{branch_name}")
            base_sha = ref.object.sha
            base_commit = repo.get_git_commit(base_sha)
            base_tree = base_commit.tree

            # Build tree elements for all files
            tree_elements = [
                InputGitTreeElement(
                    path=path,
                    mode="100755" if path in executable_paths else "100644",
                    type="blob",
                    content=content,
                )
                for path, content in files.items()
            ]

            new_tree = repo.create_git_tree(tree_elements, base_tree)
            new_commit = repo.create_git_commit(
                message=commit_message,
                tree=new_tree,
                parents=[base_commit],
            )
            ref.edit(sha=new_commit.sha)
            return new_commit.sha
        except GithubException as e:
            if e.status == 401:
                raise AuthorizationError("Invalid GitHub token")
            raise ValidationError(f"Failed to commit files: {e}")

    def find_open_pull_request(
        self, repo_full_name: str, branch_name: str, base_branch: str
    ) -> dict[str, Any] | None:
        """Find an existing open PR from branch_name into base_branch. Returns {url, number} or None."""
        try:
            repo = self._client.get_repo(repo_full_name)
            pulls = repo.get_pulls(state="open", head=f"{repo.owner.login}:{branch_name}", base=base_branch)
            for pr in pulls:
                return {"url": pr.html_url, "number": pr.number}
            return None
        except GithubException as e:
            if e.status == 401:
                raise AuthorizationError("Invalid GitHub token")
            return None

    def update_pull_request(
        self, repo_full_name: str, pr_number: int, body: str
    ) -> None:
        """Update the body of an existing pull request."""
        try:
            repo = self._client.get_repo(repo_full_name)
            pr = repo.get_pull(pr_number)
            pr.edit(body=body)
        except GithubException as e:
            if e.status == 401:
                raise AuthorizationError("Invalid GitHub token")
            raise ValidationError(f"Failed to update PR #{pr_number}: {e}")

    def create_pull_request(
        self,
        repo_full_name: str,
        branch_name: str,
        base_branch: str,
        title: str,
        body: str,
    ) -> dict[str, Any]:
        """Create a pull request. Returns {url, number}."""
        try:
            repo = self._client.get_repo(repo_full_name)
            pr = repo.create_pull(
                title=title,
                body=body,
                head=branch_name,
                base=base_branch,
            )
            return {"url": pr.html_url, "number": pr.number}
        except GithubException as e:
            if e.status == 401:
                raise AuthorizationError("Invalid GitHub token")
            if e.status == 422:
                raise ValidationError(f"Failed to create PR (may already exist): {e}")
            raise ValidationError(f"Failed to create pull request: {e}")
