"""Tests for prompt management API routes."""
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routes.prompts import router
from domain.entities.analysis_prompt import AnalysisPrompt
from domain.entities.prompt_revision import PromptRevision


def _make_prompt(**overrides):
    """Create an AnalysisPrompt with sensible defaults."""
    defaults = dict(
        id="p1",
        user_id=None,
        name="Discovery",
        description="Discover architecture",
        category="discovery",
        prompt_template="Analyze {repo}",
        variables=["repo"],
        is_default=True,
        created_at=datetime.now(timezone.utc),
        updated_at=None,
        key="discovery",
        type="prompt",
    )
    defaults.update(overrides)
    return AnalysisPrompt(**defaults)


def _make_revision(**overrides):
    """Create a PromptRevision with sensible defaults."""
    defaults = dict(
        id="r1",
        prompt_id="p1",
        revision_number=1,
        prompt_template="Old template",
        variables=["repo"],
        name="Discovery",
        description=None,
        change_summary="Initial",
        created_by=None,
        created_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    return PromptRevision(**defaults)


@pytest.fixture
def mock_prompt_service():
    """AsyncMock standing in for PromptService."""
    return AsyncMock()


@pytest.fixture
def client(mock_prompt_service):
    """TestClient with prompt router — patches _get_prompt_service to return mock."""
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    with patch(
        "api.routes.prompts._get_prompt_service",
        return_value=mock_prompt_service,
    ):
        yield TestClient(app)


# -------------------------------------------------------------------
# 1. List all prompts
# -------------------------------------------------------------------

def test_list_prompts_returns_all(client, mock_prompt_service):
    """GET /api/v1/prompts/ returns all prompts with expected fields."""
    prompts = [
        _make_prompt(id="p1", key="discovery"),
        _make_prompt(id="p2", key="observation", name="Observation"),
        _make_prompt(id="p3", key="synthesis", name="Synthesis"),
    ]
    mock_prompt_service.get_all_prompts.return_value = prompts

    resp = client.get("/api/v1/prompts/")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 3
    for item in data:
        assert "key" in item


# -------------------------------------------------------------------
# 2. Get a single prompt
# -------------------------------------------------------------------

def test_get_single_prompt(client, mock_prompt_service):
    """GET /api/v1/prompts/{id} returns the correct prompt."""
    prompt = _make_prompt(id="p1", name="Discovery")
    mock_prompt_service.get_prompt.return_value = prompt

    resp = client.get("/api/v1/prompts/p1")

    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Discovery"
    assert data["id"] == "p1"


# -------------------------------------------------------------------
# 3. Prompt not found
# -------------------------------------------------------------------

def test_get_prompt_not_found(client, mock_prompt_service):
    """GET /api/v1/prompts/{id} returns 404 when prompt does not exist."""
    mock_prompt_service.get_prompt.side_effect = ValueError("not found")

    resp = client.get("/api/v1/prompts/nonexistent")

    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"]


# -------------------------------------------------------------------
# 4. Update a prompt
# -------------------------------------------------------------------

def test_update_prompt_via_api(client, mock_prompt_service):
    """PUT /api/v1/prompts/{id} updates the prompt and returns new state."""
    updated = _make_prompt(
        id="p1",
        name="Discovery v2",
        prompt_template="New template for {repo}",
    )
    mock_prompt_service.update_prompt.return_value = updated

    body = {
        "name": "Discovery v2",
        "prompt_template": "New template for {repo}",
        "change_summary": "Rewrote the prompt",
    }
    resp = client.put("/api/v1/prompts/p1", json=body)

    assert resp.status_code == 200
    data = resp.json()
    assert data["prompt_template"] == "New template for {repo}"
    assert data["name"] == "Discovery v2"

    # Verify the service was called with the correct keyword arguments
    mock_prompt_service.update_prompt.assert_called_once_with(
        prompt_id="p1",
        name="Discovery v2",
        description=None,
        prompt_template="New template for {repo}",
        variables=None,
        change_summary="Rewrote the prompt",
    )


# -------------------------------------------------------------------
# 5. List revisions
# -------------------------------------------------------------------

def test_get_revisions_after_update(client, mock_prompt_service):
    """GET /api/v1/prompts/{id}/revisions returns revision history."""
    revisions = [
        _make_revision(id="r1", revision_number=1, prompt_template="First draft"),
        _make_revision(id="r2", revision_number=2, prompt_template="Second draft"),
    ]
    mock_prompt_service.get_revision_history.return_value = revisions

    resp = client.get("/api/v1/prompts/p1/revisions")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["revision_number"] == 1
    assert data[1]["revision_number"] == 2


# -------------------------------------------------------------------
# 6. Revert to a previous revision
# -------------------------------------------------------------------

def test_revert_via_api(client, mock_prompt_service):
    """POST /api/v1/prompts/{id}/revert/{rev_id} restores old content."""
    reverted = _make_prompt(
        id="p1",
        name="Discovery",
        prompt_template="Old template",
    )
    mock_prompt_service.revert_to_revision.return_value = reverted

    resp = client.post("/api/v1/prompts/p1/revert/r1")

    assert resp.status_code == 200
    data = resp.json()
    assert data["prompt_template"] == "Old template"

    mock_prompt_service.revert_to_revision.assert_called_once_with("p1", "r1")
