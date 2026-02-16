"""Tests for prompt management: PromptService, DatabasePromptLoader, and seeder.

Covers:
- Seeder: populating empty database, skipping when populated, preserving keys
- DatabasePromptLoader: cache behavior, key lookup, invalidation
- PromptService: update with revisions, revert, revision history
"""
from pathlib import Path

import pytest
from unittest.mock import AsyncMock, MagicMock

from domain.entities.analysis_prompt import AnalysisPrompt
from domain.entities.prompt_revision import PromptRevision
from infrastructure.prompts.database_prompt_loader import DatabasePromptLoader
from infrastructure.prompts.prompt_seeder import seed_default_prompts
from application.services.prompt_service import PromptService


# ── In-memory mock repositories ──────────────────────────────────────────────


class MockPromptRepo:
    """In-memory mock for PromptRepository."""

    def __init__(self, prompts=None):
        self._prompts = {p.id: p for p in (prompts or [])}

    async def get_by_id(self, id):
        return self._prompts.get(id)

    async def get_by_key(self, key):
        for p in self._prompts.values():
            if p.key == key:
                return p
        return None

    async def get_all_defaults(self):
        return [p for p in self._prompts.values() if p.is_default]

    async def get_all(self, limit=100, offset=0):
        return list(self._prompts.values())[offset : offset + limit]

    async def count_defaults(self):
        return sum(1 for p in self._prompts.values() if p.is_default)

    async def add(self, entity):
        self._prompts[entity.id] = entity
        return entity

    async def update(self, entity):
        self._prompts[entity.id] = entity
        return entity

    async def delete(self, id):
        return self._prompts.pop(id, None) is not None


class MockRevisionRepo:
    """In-memory mock for PromptRevisionRepository."""

    def __init__(self, revisions=None):
        self._revisions = {r.id: r for r in (revisions or [])}

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

    async def delete(self, id):
        return self._revisions.pop(id, None) is not None


# ── Helpers ───────────────────────────────────────────────────────────────────

PROMPTS_JSON_PATH = Path(__file__).parent.parent.parent.parent / "prompts.json"

EXPECTED_KEYS = {
    "discovery",
    "layers",
    "patterns",
    "communication",
    "technology",
    "frontend_analysis",
    "blueprint_synthesis",
}


def _make_prompt(key="test_key", name="Test", template="Hello {name}", **kwargs):
    """Shorthand factory for test prompts."""
    return AnalysisPrompt.create(
        name=name,
        category=kwargs.pop("category", "test"),
        prompt_template=template,
        is_default=kwargs.pop("is_default", True),
        key=key,
        **kwargs,
    )


def _make_revision(prompt_id, revision_number=1, template="old template", **kwargs):
    """Shorthand factory for test revisions."""
    return PromptRevision.create(
        prompt_id=prompt_id,
        revision_number=revision_number,
        prompt_template=template,
        variables=kwargs.pop("variables", ["var1"]),
        name=kwargs.pop("name", "Old Name"),
        description=kwargs.pop("description", "Old description"),
        change_summary=kwargs.pop("change_summary", "test change"),
        created_by=kwargs.pop("created_by", None),
    )


# ══════════════════════════════════════════════════════════════════════════════
# Seeder tests
# ══════════════════════════════════════════════════════════════════════════════


class TestSeedDefaultPrompts:
    """Tests for seed_default_prompts()."""

    @pytest.mark.asyncio
    async def test_seed_populates_empty_database(self):
        """When no defaults exist, seeder reads prompts.json and inserts all 7 prompts."""
        repo = MockPromptRepo()
        # Wrap add so we can count calls
        original_add = repo.add
        repo.add = AsyncMock(side_effect=original_add)

        count = await seed_default_prompts(repo, prompts_file=PROMPTS_JSON_PATH)

        assert count == 7
        assert repo.add.call_count == 7

    @pytest.mark.asyncio
    async def test_seed_skips_if_already_populated(self):
        """When defaults already exist, seeder inserts nothing and returns 0."""
        # Pre-populate with 5 default prompts
        prompts = [_make_prompt(key=f"key_{i}") for i in range(5)]
        repo = MockPromptRepo(prompts)
        repo.add = AsyncMock()

        count = await seed_default_prompts(repo, prompts_file=PROMPTS_JSON_PATH)

        assert count == 0
        repo.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_seed_preserves_prompt_keys(self):
        """All 7 prompt keys from prompts.json are preserved on the inserted entities."""
        repo = MockPromptRepo()
        original_add = repo.add
        repo.add = AsyncMock(side_effect=original_add)

        await seed_default_prompts(repo, prompts_file=PROMPTS_JSON_PATH)

        inserted_keys = set()
        for call_args in repo.add.call_args_list:
            prompt = call_args[0][0]
            assert isinstance(prompt, AnalysisPrompt)
            assert prompt.is_default is True
            inserted_keys.add(prompt.key)

        assert inserted_keys == EXPECTED_KEYS


# ══════════════════════════════════════════════════════════════════════════════
# DatabasePromptLoader tests
# ══════════════════════════════════════════════════════════════════════════════


class TestDatabasePromptLoader:
    """Tests for DatabasePromptLoader caching and lookup."""

    @pytest.mark.asyncio
    async def test_get_prompt_by_key_returns_correct_prompt(self):
        """Loader returns the matching prompt from the repo."""
        prompt = _make_prompt(key="discovery", name="Discovery Analysis")
        repo = MockPromptRepo([prompt])
        loader = DatabasePromptLoader(repo)

        result = await loader.get_prompt_by_key("discovery")

        assert result.key == "discovery"
        assert result.name == "Discovery Analysis"
        assert result.id == prompt.id

    @pytest.mark.asyncio
    async def test_get_prompt_by_key_caches_after_first_load(self):
        """Second call for the same key uses cache, not the DB."""
        prompt = _make_prompt(key="layers")
        repo = MockPromptRepo([prompt])
        repo.get_by_key = AsyncMock(return_value=prompt)
        loader = DatabasePromptLoader(repo)

        await loader.get_prompt_by_key("layers")
        await loader.get_prompt_by_key("layers")

        repo.get_by_key.assert_called_once_with("layers")

    @pytest.mark.asyncio
    async def test_get_prompt_by_key_raises_on_missing_key(self):
        """Loader raises ValueError when the key does not exist."""
        repo = MockPromptRepo()
        loader = DatabasePromptLoader(repo)

        with pytest.raises(ValueError, match="not found"):
            await loader.get_prompt_by_key("nonexistent_key")

    @pytest.mark.asyncio
    async def test_invalidate_cache_forces_reload(self):
        """After invalidation, the next call re-fetches from the DB."""
        prompt = _make_prompt(key="patterns")
        repo = MockPromptRepo([prompt])
        repo.get_by_key = AsyncMock(return_value=prompt)
        loader = DatabasePromptLoader(repo)

        await loader.get_prompt_by_key("patterns")
        loader.invalidate_cache()
        await loader.get_prompt_by_key("patterns")

        assert repo.get_by_key.call_count == 2

    @pytest.mark.asyncio
    async def test_get_all_default_prompts(self):
        """get_all_default_prompts returns all defaults and caches them by key."""
        prompts = [
            _make_prompt(key="discovery"),
            _make_prompt(key="layers"),
            _make_prompt(key="patterns"),
        ]
        repo = MockPromptRepo(prompts)
        repo.get_all_defaults = AsyncMock(return_value=prompts)
        loader = DatabasePromptLoader(repo)

        result = await loader.get_all_default_prompts()

        assert len(result) == 3
        repo.get_all_defaults.assert_called_once()

        # Verify caching: a second call should NOT hit the repo again
        result2 = await loader.get_all_default_prompts()
        assert len(result2) == 3
        repo.get_all_defaults.assert_called_once()


# ══════════════════════════════════════════════════════════════════════════════
# PromptService tests
# ══════════════════════════════════════════════════════════════════════════════


class TestPromptService:
    """Tests for PromptService business logic."""

    def _build_service(self, prompt, revisions=None):
        """Create a PromptService with mock repos pre-loaded with data."""
        prompt_repo = MockPromptRepo([prompt])
        revision_repo = MockRevisionRepo(revisions or [])
        loader = DatabasePromptLoader(prompt_repo)
        # Spy on invalidate_cache
        loader.invalidate_cache = MagicMock()
        service = PromptService(prompt_repo, revision_repo, loader)
        return service, prompt_repo, revision_repo, loader

    @pytest.mark.asyncio
    async def test_update_prompt_creates_revision(self):
        """update_prompt saves the OLD template as a revision before applying changes."""
        prompt = _make_prompt(key="discovery", template="Original template")
        service, prompt_repo, revision_repo, loader = self._build_service(prompt)
        original_add = revision_repo.add
        revision_repo.add = AsyncMock(side_effect=original_add)

        await service.update_prompt(
            prompt_id=prompt.id,
            prompt_template="Updated template",
            change_summary="Improved wording",
        )

        revision_repo.add.assert_called_once()
        saved_revision = revision_repo.add.call_args[0][0]
        assert isinstance(saved_revision, PromptRevision)
        assert saved_revision.prompt_template == "Original template"
        assert saved_revision.prompt_id == prompt.id

    @pytest.mark.asyncio
    async def test_update_prompt_applies_changes(self):
        """After update, the prompt has the new template text."""
        prompt = _make_prompt(key="layers", template="Old text")
        service, prompt_repo, revision_repo, loader = self._build_service(prompt)
        original_update = prompt_repo.update
        prompt_repo.update = AsyncMock(side_effect=original_update)

        result = await service.update_prompt(
            prompt_id=prompt.id,
            prompt_template="New text",
            name="Renamed Prompt",
        )

        prompt_repo.update.assert_called_once()
        updated_prompt = prompt_repo.update.call_args[0][0]
        assert updated_prompt.prompt_template == "New text"
        assert updated_prompt.name == "Renamed Prompt"
        assert result.prompt_template == "New text"

    @pytest.mark.asyncio
    async def test_update_prompt_invalidates_cache(self):
        """update_prompt calls invalidate_cache on the loader."""
        prompt = _make_prompt(key="patterns", template="Some template")
        service, prompt_repo, revision_repo, loader = self._build_service(prompt)

        await service.update_prompt(
            prompt_id=prompt.id,
            prompt_template="Changed template",
        )

        loader.invalidate_cache.assert_called_once()

    @pytest.mark.asyncio
    async def test_revision_history_ordered_by_number(self):
        """get_revision_history returns revisions as provided by the repo."""
        prompt = _make_prompt(key="communication")
        rev1 = _make_revision(prompt.id, revision_number=1, template="v1")
        rev2 = _make_revision(prompt.id, revision_number=2, template="v2")
        rev3 = _make_revision(prompt.id, revision_number=3, template="v3")
        service, prompt_repo, revision_repo, loader = self._build_service(
            prompt, revisions=[rev1, rev2, rev3]
        )

        history = await service.get_revision_history(prompt.id)

        assert len(history) == 3
        # MockRevisionRepo returns newest first (desc by revision_number)
        assert history[0].revision_number == 3
        assert history[1].revision_number == 2
        assert history[2].revision_number == 1

    @pytest.mark.asyncio
    async def test_revert_restores_old_content(self):
        """revert_to_revision applies the revision's template to the prompt."""
        prompt = _make_prompt(key="technology", template="Current template")
        old_revision = _make_revision(
            prompt.id,
            revision_number=1,
            template="Reverted template",
            variables=["old_var"],
            name="Old Name",
            description="Old desc",
        )
        service, prompt_repo, revision_repo, loader = self._build_service(
            prompt, revisions=[old_revision]
        )
        original_update = prompt_repo.update
        prompt_repo.update = AsyncMock(side_effect=original_update)

        result = await service.revert_to_revision(
            prompt_id=prompt.id,
            revision_id=old_revision.id,
            user_id="user-123",
        )

        prompt_repo.update.assert_called_once()
        updated_prompt = prompt_repo.update.call_args[0][0]
        assert updated_prompt.prompt_template == "Reverted template"
        assert updated_prompt.variables == ["old_var"]
        assert result.prompt_template == "Reverted template"

    @pytest.mark.asyncio
    async def test_revert_creates_new_revision(self):
        """revert_to_revision creates an audit-trail revision with the pre-revert state."""
        prompt = _make_prompt(key="frontend_analysis", template="Before revert")
        old_revision = _make_revision(
            prompt.id,
            revision_number=1,
            template="Ancient template",
        )
        service, prompt_repo, revision_repo, loader = self._build_service(
            prompt, revisions=[old_revision]
        )
        original_add = revision_repo.add
        revision_repo.add = AsyncMock(side_effect=original_add)

        await service.revert_to_revision(
            prompt_id=prompt.id,
            revision_id=old_revision.id,
        )

        revision_repo.add.assert_called_once()
        audit_revision = revision_repo.add.call_args[0][0]
        assert isinstance(audit_revision, PromptRevision)
        # The audit revision should capture the state BEFORE the revert
        assert audit_revision.prompt_template == "Before revert"
        assert "revert" in audit_revision.change_summary.lower()
        assert audit_revision.revision_number == 2  # next after existing rev 1
