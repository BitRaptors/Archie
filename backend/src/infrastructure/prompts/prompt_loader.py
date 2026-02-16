"""Prompt loader from JSON file."""
import json
from pathlib import Path
from typing import Any
from domain.entities.analysis_prompt import AnalysisPrompt
from config.constants import PromptCategory


class PromptLoader:
    """Loads prompts from prompts.json file."""

    def __init__(self, prompts_file: Path | None = None):
        """Initialize prompt loader.
        
        Args:
            prompts_file: Path to prompts.json file. If None, uses default location.
        """
        if prompts_file is None:
            # Default to backend/prompts.json relative to this file
            backend_dir = Path(__file__).parent.parent.parent.parent
            prompts_file = backend_dir / "prompts.json"
        
        self._prompts_file = prompts_file
        self._prompts_cache: dict[str, Any] | None = None

    def _load_prompts(self) -> dict[str, Any]:
        """Load prompts from JSON file."""
        if self._prompts_cache is not None:
            return self._prompts_cache
        
        if not self._prompts_file.exists():
            raise FileNotFoundError(f"Prompts file not found: {self._prompts_file}")
        
        with open(self._prompts_file, "r", encoding="utf-8") as f:
            self._prompts_cache = json.load(f)
        
        return self._prompts_cache

    def get_prompt_by_key(self, key: str) -> AnalysisPrompt:
        """Get a prompt by key.
        
        Args:
            key: Prompt key (e.g., "directory_summary", "patterns")
        
        Returns:
            AnalysisPrompt entity
        """
        prompts_data = self._load_prompts()
        
        if "prompts" not in prompts_data:
            raise ValueError("'prompts' section not found in prompts.json")
        
        if key not in prompts_data["prompts"]:
            raise ValueError(f"Prompt key '{key}' not found in prompts.json")
        
        prompt_data = prompts_data["prompts"][key]
        return AnalysisPrompt.create(
            name=prompt_data["name"],
            category=prompt_data["category"],
            prompt_template=prompt_data["prompt_template"],
            variables=prompt_data.get("variables", []),
            is_default=prompt_data.get("is_default", False),
        )

    def get_prompt_by_category(self, category: str) -> AnalysisPrompt | None:
        """Get a prompt by category.
        
        Args:
            category: Prompt category (e.g., "directory_summary", "patterns")
        
        Returns:
            AnalysisPrompt entity or None if not found
        """
        prompts_data = self._load_prompts()
        
        if "prompts" not in prompts_data:
            return None
        
        for key, prompt_data in prompts_data["prompts"].items():
            if prompt_data["category"] == category:
                return AnalysisPrompt.create(
                    name=prompt_data["name"],
                    category=prompt_data["category"],
                    prompt_template=prompt_data["prompt_template"],
                    variables=prompt_data.get("variables", []),
                    is_default=prompt_data.get("is_default", False),
                )
        
        return None

    def get_all_default_prompts(self) -> list[AnalysisPrompt]:
        """Get all prompts (all are defaults now)."""
        prompts_data = self._load_prompts()
        prompts = []
        
        for key, prompt_data in prompts_data.get("prompts", {}).items():
            prompts.append(AnalysisPrompt.create(
                name=prompt_data["name"],
                category=prompt_data["category"],
                prompt_template=prompt_data["prompt_template"],
                variables=prompt_data.get("variables", []),
                is_default=prompt_data.get("is_default", False),
            ))
        
        return prompts

    def get_unified_blueprint_prompt(self) -> AnalysisPrompt:
        """Get the unified blueprint generation prompt."""
        return self.get_prompt_by_key("unified_blueprint")

