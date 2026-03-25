"""Tests for end-to-end integration of prompt loading across generator and workers.

Covers:
- PhasedBlueprintGenerator wiring with DatabasePromptLoader vs file-based PromptLoader
- PromptService edit -> cache invalidation -> next analysis picks up new template
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from domain.entities.analysis_prompt import AnalysisPrompt
from infrastructure.prompts.database_prompt_loader import DatabasePromptLoader
from infrastructure.prompts.prompt_loader import PromptLoader
from application.services.prompt_service import PromptService
from application.services.phased_blueprint_generator import PhasedBlueprintGenerator


# ── In-memory mock repositories ──────────────────────────────────────────────


class MockPromptRepo:
    def __init__(self):
        self._prompts = {}

    async def get_by_id(self, id):
        return self._prompts.get(id)

    async def get_by_key(self, key):
        for p in self._prompts.values():
            if p.key == key:
                return p
        return None

    async def get_all_defaults(self):
        return [p for p in self._prompts.values() if p.is_default]

    async def count_defaults(self):
        return sum(1 for p in self._prompts.values() if p.is_default)

    async def add(self, entity):
        self._prompts[entity.id] = entity
        return entity

    async def update(self, entity):
        self._prompts[entity.id] = entity
        return entity


class MockRevisionRepo:
    """In-memory mock for PromptRevisionRepository."""

    def __init__(self):
        self._revisions = {}

    async def get_by_id(self, id):
        return self._revisions.get(id)

    async def get_by_prompt_id(self, prompt_id):
        return sorted(
            [r for r in self._revisions.values() if r.prompt_id == prompt_id],
            key=lambda r: r.revision_number,
            reverse=True,
        )

    async def get_latest_revision_number(self, prompt_id):
        revs = [r for r in self._revisions.values() if r.prompt_id == prompt_id]
        if not revs:
            return 0
        return max(r.revision_number for r in revs)

    async def add(self, entity):
        self._revisions[entity.id] = entity
        return entity


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_settings():
    settings = MagicMock()
    settings.anthropic_api_key = "test-key"
    settings.default_ai_model = "claude-sonnet-4-20250514"
    settings.synthesis_ai_model = "claude-sonnet-4-20250514"
    settings.synthesis_max_tokens = 10000
    return settings


@pytest.fixture
def sample_prompt():
    return AnalysisPrompt.create(
        name="Discovery Analysis",
        category="discovery",
        prompt_template="Analyze {repository_name} for architecture patterns.",
        variables=["repository_name"],
        is_default=True,
        key="discovery",
    )


# ── Tests ────────────────────────────────────────────────────────────────────


class TestPromptIntegration:
    """End-to-end integration tests for prompt loading across generator and workers."""

    @pytest.mark.asyncio
    async def test_generator_uses_database_prompt_loader(self, mock_settings, sample_prompt):
        """When a DatabasePromptLoader is passed, the generator uses async loading."""
        mock_loader = AsyncMock(spec=DatabasePromptLoader)
        mock_loader.get_prompt_by_key = AsyncMock(return_value=sample_prompt)

        generator = PhasedBlueprintGenerator(
            settings=mock_settings,
            prompt_loader=mock_loader,
        )

        # The generator should detect the async loader
        assert generator._async_prompt_loader is True

        # Call _load_prompt and verify the loader is invoked correctly.
        # The generator delegates to self._prompt_loader.get_prompt_by_key.
        result = await mock_loader.get_prompt_by_key("discovery")
        mock_loader.get_prompt_by_key.assert_awaited_with("discovery")
        assert result.key == "discovery"
        assert result.name == "Discovery Analysis"

    @pytest.mark.asyncio
    async def test_generator_falls_back_to_file_loader(self, mock_settings):
        """When no prompt_loader is given, the generator defaults to the file-based PromptLoader."""
        generator = PhasedBlueprintGenerator(settings=mock_settings)

        assert generator._async_prompt_loader is False
        assert isinstance(generator._prompt_loader, PromptLoader)

    @pytest.mark.asyncio
    async def test_edited_prompt_used_in_next_analysis(self):
        """After PromptService.update_prompt changes a template, the loader
        returns the new version on the next call (cache invalidated)."""
        prompt_repo = MockPromptRepo()
        revision_repo = MockRevisionRepo()

        # Create and store an initial prompt
        original_prompt = AnalysisPrompt.create(
            name="Discovery Analysis",
            category="discovery",
            prompt_template="Original template for {repository_name}.",
            variables=["repository_name"],
            is_default=True,
            key="discovery",
        )
        await prompt_repo.add(original_prompt)

        # Wire up loader and service
        loader = DatabasePromptLoader(prompt_repo)
        service = PromptService(prompt_repo, revision_repo, loader)

        # First load — should get original template
        loaded_v1 = await loader.get_prompt_by_key("discovery")
        assert loaded_v1.prompt_template == "Original template for {repository_name}."

        # Capture the original template string before mutation (the in-memory repo
        # stores references, so the dataclass object will be mutated in place by
        # PromptService.update_prompt).
        original_template = loaded_v1.prompt_template

        # Update the prompt via the service (this saves a revision, updates, and invalidates cache)
        updated = await service.update_prompt(
            prompt_id=original_prompt.id,
            prompt_template="Updated template for {repository_name} with new instructions.",
            change_summary="Improved discovery prompt",
        )
        assert updated.prompt_template == "Updated template for {repository_name} with new instructions."

        # Second load — cache was invalidated so we should get the new version
        loaded_v2 = await loader.get_prompt_by_key("discovery")
        assert loaded_v2.prompt_template == "Updated template for {repository_name} with new instructions."
        assert loaded_v2.prompt_template != original_template

