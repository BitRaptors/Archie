"""Tests for MCP resources (BlueprintResources)."""
import pytest
from pathlib import Path

from domain.entities.blueprint import (
    BlueprintMeta,
    StructuredBlueprint,
)
from infrastructure.mcp.resources import BlueprintResources


class TestBlueprintResources:
    """Test the BlueprintResources class."""

    @pytest.fixture
    def resources(self, tmp_path):
        """Set up resources with test blueprint."""
        storage_dir = tmp_path / "storage"
        bp_dir = storage_dir / "blueprints" / "repo-1"
        bp_dir.mkdir(parents=True)

        bp = StructuredBlueprint(
            meta=BlueprintMeta(repository="owner/test-repo", repository_id="repo-1"),
        )
        (bp_dir / "blueprint.json").write_text(
            bp.model_dump_json(indent=2), encoding="utf-8"
        )
        return BlueprintResources(storage_dir=storage_dir)

    def test_get_resource_analyzed_list(self, resources):
        result = resources.get_resource("blueprint://analyzed")
        assert result is not None
        mime, content = result
        assert mime == "text/markdown"
        assert "owner/test-repo" in content

    def test_get_resource_full_blueprint(self, resources):
        result = resources.get_resource("blueprint://analyzed/repo-1")
        assert result is not None
        mime, content = result
        assert mime == "text/markdown"
        assert len(content) > 0

    def test_get_resource_unknown_uri(self, resources):
        result = resources.get_resource("unknown://something")
        assert result is None

    def test_get_resource_nonexistent_repo(self, resources):
        result = resources.get_resource("blueprint://analyzed/nonexistent")
        assert result is not None
        mime, content = result
        assert "not found" in content.lower()

    def test_get_resource_nonexistent_section(self, resources):
        result = resources.get_resource("blueprint://analyzed/repo-1/nonexistent-section")
        assert result is not None
        mime, content = result
        assert "not found" in content.lower() or "Available" in content

    @pytest.mark.asyncio
    async def test_list_resources(self, resources):
        result = await resources.list_resources()
        assert len(result) > 0
        uris = [str(r.uri) for r in result]
        assert any("repo-1" in u for u in uris)

    def test_empty_storage(self, tmp_path):
        storage_dir = tmp_path / "empty_storage"
        storage_dir.mkdir()
        res = BlueprintResources(storage_dir=storage_dir)
        result = res.get_resource("blueprint://analyzed")
        mime, content = result
        assert "No analyzed" in content or "No successfully" in content

    def test_multiple_repos(self, tmp_path):
        """Multiple repos should all appear in the analyzed list."""
        storage_dir = tmp_path / "storage"

        for rid, name in [("repo-a", "org/alpha"), ("repo-b", "org/beta")]:
            bp_dir = storage_dir / "blueprints" / rid
            bp_dir.mkdir(parents=True)
            bp = StructuredBlueprint(
                meta=BlueprintMeta(repository=name, repository_id=rid),
            )
            (bp_dir / "blueprint.json").write_text(
                bp.model_dump_json(indent=2), encoding="utf-8"
            )

        res = BlueprintResources(storage_dir=storage_dir)
        mime, content = res.get_resource("blueprint://analyzed")
        assert "org/alpha" in content
        assert "org/beta" in content
