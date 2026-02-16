"""Prompt service — business logic for prompt CRUD, revisions, and revert."""
from datetime import datetime, timezone
from domain.entities.analysis_prompt import AnalysisPrompt
from domain.entities.prompt_revision import PromptRevision
from infrastructure.persistence.prompt_repository import PromptRepository
from infrastructure.persistence.prompt_revision_repository import PromptRevisionRepository
from infrastructure.prompts.database_prompt_loader import DatabasePromptLoader


class PromptService:
    """Service for managing analysis prompts with revision history."""

    def __init__(
        self,
        prompt_repo: PromptRepository,
        revision_repo: PromptRevisionRepository,
        prompt_loader: DatabasePromptLoader,
    ):
        self._prompt_repo = prompt_repo
        self._revision_repo = revision_repo
        self._prompt_loader = prompt_loader

    async def get_all_prompts(self) -> list[AnalysisPrompt]:
        """List all prompts for the Settings UI."""
        return await self._prompt_repo.get_all_defaults()

    async def get_prompt(self, prompt_id: str) -> AnalysisPrompt:
        """Get a single prompt by ID."""
        prompt = await self._prompt_repo.get_by_id(prompt_id)
        if not prompt:
            raise ValueError(f"Prompt not found: {prompt_id}")
        return prompt

    async def update_prompt(
        self,
        prompt_id: str,
        name: str | None = None,
        description: str | None = None,
        prompt_template: str | None = None,
        variables: list[str] | None = None,
        change_summary: str | None = None,
        user_id: str | None = None,
    ) -> AnalysisPrompt:
        """Update a prompt, saving the current state as a revision first."""
        prompt = await self.get_prompt(prompt_id)

        # Save current state as a revision before applying changes
        next_rev = await self._revision_repo.get_latest_revision_number(prompt_id) + 1
        revision = PromptRevision.create(
            prompt_id=prompt_id,
            revision_number=next_rev,
            prompt_template=prompt.prompt_template,
            variables=list(prompt.variables),
            name=prompt.name,
            description=prompt.description,
            change_summary=change_summary or "Manual edit",
            created_by=user_id,
        )
        await self._revision_repo.add(revision)

        # Apply updates
        if name is not None:
            prompt.name = name
        if description is not None:
            prompt.description = description
        if prompt_template is not None:
            prompt.prompt_template = prompt_template
        if variables is not None:
            prompt.variables = variables
        prompt.updated_at = datetime.now(timezone.utc)

        updated = await self._prompt_repo.update(prompt)
        self._prompt_loader.invalidate_cache()
        return updated

    async def get_revision_history(self, prompt_id: str) -> list[PromptRevision]:
        """List revisions for a prompt, newest first."""
        # Ensure prompt exists
        await self.get_prompt(prompt_id)
        return await self._revision_repo.get_by_prompt_id(prompt_id)

    async def revert_to_revision(
        self,
        prompt_id: str,
        revision_id: str,
        user_id: str | None = None,
    ) -> AnalysisPrompt:
        """Revert a prompt to a previous revision.

        Creates a new revision entry (audit trail) then applies the old content.
        """
        prompt = await self.get_prompt(prompt_id)
        revision = await self._revision_repo.get_by_id(revision_id)
        if not revision or revision.prompt_id != prompt_id:
            raise ValueError(f"Revision not found: {revision_id}")

        # Save current state as a new revision (audit trail)
        next_rev = await self._revision_repo.get_latest_revision_number(prompt_id) + 1
        audit_revision = PromptRevision.create(
            prompt_id=prompt_id,
            revision_number=next_rev,
            prompt_template=prompt.prompt_template,
            variables=list(prompt.variables),
            name=prompt.name,
            description=prompt.description,
            change_summary=f"Before revert to revision #{revision.revision_number}",
            created_by=user_id,
        )
        await self._revision_repo.add(audit_revision)

        # Apply revision content
        prompt.prompt_template = revision.prompt_template
        prompt.variables = list(revision.variables)
        if revision.name:
            prompt.name = revision.name
        if revision.description is not None:
            prompt.description = revision.description
        prompt.updated_at = datetime.now(timezone.utc)

        updated = await self._prompt_repo.update(prompt)
        self._prompt_loader.invalidate_cache()
        return updated
