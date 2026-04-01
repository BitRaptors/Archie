"""Prompt revision repository implementation."""
from datetime import datetime
from domain.entities.prompt_revision import PromptRevision
from domain.interfaces.database import DatabaseClient, DatabaseError


class PromptRevisionRepository:
    """Repository for prompt_revisions table."""

    TABLE = "prompt_revisions"

    def __init__(self, db: DatabaseClient):
        self._db = db

    async def get_by_id(self, id: str) -> PromptRevision | None:
        try:
            result = await (
                self._db.table(self.TABLE)
                .select("*")
                .eq("id", id)
                .maybe_single()
                .execute()
            )
            if result and result.data:
                return self._to_entity(result.data)
            return None
        except DatabaseError as e:
            if e.code == "204" or "204" in str(e):
                return None
            raise

    async def get_by_prompt_id(self, prompt_id: str) -> list[PromptRevision]:
        result = await (
            self._db.table(self.TABLE)
            .select("*")
            .eq("prompt_id", prompt_id)
            .order("revision_number", desc=True)
            .execute()
        )
        return [self._to_entity(row) for row in result.data]

    async def get_latest_revision_number(self, prompt_id: str) -> int:
        result = await (
            self._db.table(self.TABLE)
            .select("revision_number")
            .eq("prompt_id", prompt_id)
            .order("revision_number", desc=True)
            .limit(1)
            .execute()
        )
        if result.data:
            return result.data[0]["revision_number"]
        return 0

    async def add(self, entity: PromptRevision) -> PromptRevision:
        data = self._to_dict(entity)
        result = await self._db.table(self.TABLE).insert(data).execute()
        return self._to_entity(result.data[0])

    async def delete(self, id: str) -> bool:
        result = await self._db.table(self.TABLE).delete().eq("id", id).execute()
        return len(result.data) > 0

    def _to_entity(self, data: dict) -> PromptRevision:
        return PromptRevision(
            id=data["id"],
            prompt_id=data["prompt_id"],
            revision_number=data["revision_number"],
            prompt_template=data["prompt_template"],
            variables=data.get("variables") or [],
            name=data.get("name"),
            description=data.get("description"),
            change_summary=data.get("change_summary"),
            created_by=data.get("created_by"),
            created_at=datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")) if data.get("created_at") else datetime.now(),
        )

    def _to_dict(self, entity: PromptRevision) -> dict:
        return {
            "id": entity.id,
            "prompt_id": entity.prompt_id,
            "revision_number": entity.revision_number,
            "prompt_template": entity.prompt_template,
            "variables": entity.variables,
            "name": entity.name,
            "description": entity.description,
            "change_summary": entity.change_summary,
            "created_by": entity.created_by,
            "created_at": entity.created_at.isoformat(),
        }
