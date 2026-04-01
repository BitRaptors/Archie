"""Database-backed prompt loader with in-memory cache."""
import logging
from domain.entities.analysis_prompt import AnalysisPrompt
from infrastructure.persistence.prompt_repository import PromptRepository

logger = logging.getLogger(__name__)


class DatabasePromptLoader:
    """Loads prompts from the database with an in-memory cache.

    Drop-in async replacement for the file-based ``PromptLoader``.
    All public methods are async so callers must ``await`` them.
    """

    def __init__(self, prompt_repo: PromptRepository):
        self._repo = prompt_repo
        self._cache: dict[str, AnalysisPrompt] = {}
        self._all_loaded = False

    async def get_prompt_by_key(self, key: str) -> AnalysisPrompt:
        """Get a prompt by its key (e.g. "discovery", "layers").

        Uses an in-memory cache; first call per key hits the DB.

        Raises:
            ValueError: If the key is not found in the database.
        """
        if key in self._cache:
            return self._cache[key]

        prompt = await self._repo.get_by_key(key)
        if not prompt:
            raise ValueError(f"Prompt key '{key}' not found in database")

        self._cache[key] = prompt
        return prompt

    async def get_all_default_prompts(self) -> list[AnalysisPrompt]:
        """Return all default prompts (cached after first call)."""
        if self._all_loaded and self._cache:
            return list(self._cache.values())

        prompts = await self._repo.get_all_defaults()
        for p in prompts:
            if p.key:
                self._cache[p.key] = p
        self._all_loaded = True
        return prompts

    def invalidate_cache(self) -> None:
        """Clear the in-memory cache so the next call re-fetches from DB."""
        self._cache.clear()
        self._all_loaded = False
        logger.debug("DatabasePromptLoader cache invalidated")
