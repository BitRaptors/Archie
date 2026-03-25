"""ManifestManager — incremental update tracking for intent layer generation."""
from __future__ import annotations

import hashlib
import json
import logging

from domain.entities.intent_layer import GenerationManifest, FolderManifestEntry

logger = logging.getLogger(__name__)


def _content_hash(content: str) -> str:
    """SHA-256 hash of file content."""
    return hashlib.sha256(content.encode()).hexdigest()


class ManifestManager:
    """Manages generation manifests for incremental intent layer updates."""

    def __init__(self, storage):
        self._storage = storage

    async def load(self, repo_id: str) -> GenerationManifest | None:
        """Load existing manifest for a repo, or None if not found."""
        path = f"blueprints/{repo_id}/intent_layer_manifest.json"
        try:
            if await self._storage.exists(path):
                content = await self._storage.read(path)
                text = content.decode("utf-8") if isinstance(content, bytes) else content
                data = json.loads(text)
                return GenerationManifest.model_validate(data)
        except Exception as e:
            logger.warning(f"Failed to load manifest for {repo_id}: {e}")
        return None

    async def save(self, repo_id: str, manifest: GenerationManifest) -> None:
        """Save manifest to storage."""
        path = f"blueprints/{repo_id}/intent_layer_manifest.json"
        data = manifest.model_dump(mode="json")
        content = json.dumps(data, indent=2)
        await self._storage.save(path, content.encode("utf-8"))

    @staticmethod
    def diff(
        old_manifest: GenerationManifest | None,
        new_files: dict[str, str],
        new_blueprint_hash: str,
    ) -> tuple[dict[str, str], set[str]]:
        """Compare new files against old manifest.

        Returns:
            (changed_files, unchanged_paths) where changed_files is the subset
            of new_files that differ from the old manifest.
        """
        if old_manifest is None or old_manifest.blueprint_hash != new_blueprint_hash:
            # Blueprint changed — everything is new
            return dict(new_files), set()

        old_hashes = {e.path: e.content_hash for e in old_manifest.entries}

        changed: dict[str, str] = {}
        unchanged: set[str] = set()

        for path, content in new_files.items():
            new_hash = _content_hash(content)
            if old_hashes.get(path) == new_hash:
                unchanged.add(path)
            else:
                changed[path] = content

        return changed, unchanged

    @staticmethod
    def build_manifest(
        blueprint_hash: str,
        files: dict[str, str],
    ) -> GenerationManifest:
        """Build a manifest from generated files."""
        entries = [
            FolderManifestEntry(path=path, content_hash=_content_hash(content))
            for path, content in sorted(files.items())
        ]
        return GenerationManifest(blueprint_hash=blueprint_hash, entries=entries)
