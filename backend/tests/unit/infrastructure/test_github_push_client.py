"""Tests for GitHubPushClient."""
import pytest
from unittest.mock import MagicMock, patch

from infrastructure.external.github_push_client import GitHubPushClient
from domain.exceptions.domain_exceptions import ValidationError, AuthorizationError


@pytest.fixture
def mock_repo():
    """Create a mock PyGithub Repository."""
    repo = MagicMock()
    repo.default_branch = "main"

    # Git ref mock
    ref = MagicMock()
    ref.object.sha = "abc123"
    repo.get_git_ref.return_value = ref

    # Git commit mock
    commit = MagicMock()
    commit.tree = MagicMock()
    repo.get_git_commit.return_value = commit

    # Tree / commit creation
    new_tree = MagicMock()
    repo.create_git_tree.return_value = new_tree

    new_commit = MagicMock()
    new_commit.sha = "def456"
    repo.create_git_commit.return_value = new_commit

    # PR creation
    pr = MagicMock()
    pr.html_url = "https://github.com/owner/repo/pull/1"
    pr.number = 1
    repo.create_pull.return_value = pr

    return repo


@pytest.fixture
def client(mock_repo):
    """Create a GitHubPushClient with mocked PyGithub."""
    with patch("infrastructure.external.github_push_client.Github") as MockGithub:
        instance = MockGithub.return_value
        instance.get_repo.return_value = mock_repo
        c = GitHubPushClient(token="test-token")
        yield c


class TestGetDefaultBranch:

    def test_returns_default_branch(self, client, mock_repo):
        result = client.get_default_branch("owner/repo")
        assert result == "main"

    def test_raises_on_not_found(self, client, mock_repo):
        from github.GithubException import GithubException
        mock_repo.default_branch  # access works
        # Make get_repo raise 404
        client._client.get_repo.side_effect = GithubException(404, {}, {})
        with pytest.raises(ValidationError, match="not found"):
            client.get_default_branch("owner/missing")


class TestCreateBranch:

    def test_creates_branch(self, client, mock_repo):
        result = client.create_branch("owner/repo", "feature/test", "main")
        assert result == "refs/heads/feature/test"
        mock_repo.get_git_ref.assert_called_with("heads/main")
        mock_repo.create_git_ref.assert_called_once_with(
            ref="refs/heads/feature/test", sha="abc123"
        )

    def test_raises_on_existing_branch(self, client, mock_repo):
        from github.GithubException import GithubException
        mock_repo.create_git_ref.side_effect = GithubException(422, {}, {})
        with pytest.raises(ValidationError, match="already exists"):
            client.create_branch("owner/repo", "existing", "main")


class TestCommitFiles:

    def test_commits_files_atomically(self, client, mock_repo):
        files = {"CLAUDE.md": "# Content", "AGENTS.md": "# Agents"}
        sha = client.commit_files("owner/repo", "main", files, "chore: sync")
        assert sha == "def456"

        # Verify tree creation
        mock_repo.create_git_tree.assert_called_once()
        tree_args = mock_repo.create_git_tree.call_args
        elements = tree_args[0][0]
        assert len(elements) == 2

        # Verify commit
        mock_repo.create_git_commit.assert_called_once()

        # Verify ref updated
        ref = mock_repo.get_git_ref.return_value
        ref.edit.assert_called_once_with(sha="def456")


class TestCreatePullRequest:

    def test_creates_pr(self, client, mock_repo):
        result = client.create_pull_request(
            "owner/repo", "feature/test", "main", "Title", "Body"
        )
        assert result == {"url": "https://github.com/owner/repo/pull/1", "number": 1}
        mock_repo.create_pull.assert_called_once_with(
            title="Title", body="Body", head="feature/test", base="main"
        )
