"""Prompt service."""
from typing import Any
from domain.entities.analysis_prompt import AnalysisPrompt
from domain.interfaces.repositories import IRepository
from infrastructure.prompts.default_prompts import get_default_prompts
from config.constants import PromptCategory


class PromptService:
    """Service for managing analysis prompts."""

    def __init__(self, prompt_repo: IRepository[AnalysisPrompt, str]):
        """Initialize prompt service."""
        self._repo = prompt_repo

    async def get_prompt(
        self,
        prompt_id: str,
        user_id: str | None = None,
    ) -> AnalysisPrompt:
        """Get prompt by ID."""
        prompt = await self._repo.get_by_id(prompt_id)
        if not prompt:
            raise ValueError(f"Prompt not found: {prompt_id}")
        
        # Check user access
        if prompt.user_id and prompt.user_id != user_id:
            raise ValueError("Access denied")
        
        return prompt

    async def get_default_prompts(self) -> list[AnalysisPrompt]:
        """Get all default prompts."""
        return get_default_prompts()

    async def get_prompts_by_category(
        self,
        category: str,
        user_id: str | None = None,
    ) -> list[AnalysisPrompt]:
        """Get prompts by category."""
        # Get default prompts
        defaults = [p for p in await self.get_default_prompts() if p.category == category]
        
        # Get user custom prompts
        # Would query database for user prompts
        custom = []
        
        return defaults + custom

    async def render_prompt(
        self,
        prompt_id: str,
        context: dict[str, Any],
        user_id: str | None = None,
    ) -> str:
        """Render prompt with context variables."""
        prompt = await self.get_prompt(prompt_id, user_id)
        return prompt.render(context)


