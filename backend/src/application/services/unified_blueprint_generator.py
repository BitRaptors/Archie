"""Unified blueprint generator."""
from typing import Any
import anthropic
from config.settings import get_settings
from infrastructure.storage.storage_interface import IStorage
from infrastructure.prompts.prompt_loader import PromptLoader


class UnifiedBlueprintGenerator:
    """Generates unified blueprints from multiple repositories."""

    def __init__(self, storage: IStorage):
        """Initialize unified blueprint generator."""
        settings = get_settings()
        self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self._model = settings.default_ai_model
        self._storage = storage
        self._prompt_loader = PromptLoader()

    async def generate(
        self,
        repository_ids: list[str],
        blueprint_data: list[dict[str, Any]],
        name: str = "Unified Blueprint",
    ) -> str:
        """Generate unified blueprint from multiple analyses."""
        # Aggregate patterns
        all_patterns = {}
        for data in blueprint_data:
            patterns = data.get("patterns", {})
            for pattern_type, instances in patterns.items():
                if pattern_type not in all_patterns:
                    all_patterns[pattern_type] = []
                all_patterns[pattern_type].extend(instances)
        
        # Identify common patterns
        common_patterns = self._identify_common_patterns(all_patterns, len(repository_ids))
        
        # Generate unified blueprint using AI - load prompt from prompts.json
        unified_prompt = self._prompt_loader.get_unified_blueprint_prompt()
        prompt = unified_prompt.render({
            "repository_count": str(len(repository_ids)),
            "common_patterns": str(common_patterns),
            "all_patterns": str(all_patterns),
        })
        
        response = self._client.messages.create(
            model=self._model,
            max_tokens=8000,
            messages=[{
                "role": "user",
                "content": prompt,
            }],
        )
        
        return response.content[0].text

    def _identify_common_patterns(
        self,
        all_patterns: dict[str, list],
        repo_count: int,
    ) -> dict[str, Any]:
        """Identify patterns present in most/all repos."""
        common = {}
        threshold = repo_count * 0.7  # 70% threshold
        
        for pattern_type, instances in all_patterns.items():
            if len(instances) >= threshold:
                common[pattern_type] = {
                    "frequency": len(instances),
                    "adoption_rate": len(instances) / repo_count,
                    "instances": instances,
                }
        
        return common


