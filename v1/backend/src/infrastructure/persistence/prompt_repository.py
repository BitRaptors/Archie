"""Prompt repository implementation."""
from datetime import datetime
from domain.entities.analysis_prompt import AnalysisPrompt
from domain.interfaces.database import DatabaseClient, DatabaseError


class PromptRepository:
    """Repository for analysis_prompts table."""

    TABLE = "analysis_prompts"

    def __init__(self, db: DatabaseClient):
        self._db = db

    async def get_by_id(self, id: str) -> AnalysisPrompt | None:
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

    async def get_by_key(self, key: str) -> AnalysisPrompt | None:
        try:
            result = await (
                self._db.table(self.TABLE)
                .select("*")
                .eq("key", key)
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

    async def get_all_defaults(self) -> list[AnalysisPrompt]:
        result = await (
            self._db.table(self.TABLE)
            .select("*")
            .eq("is_default", True)
            .order("name")
            .execute()
        )
        return [self._to_entity(row) for row in result.data]

    async def get_all(self, limit: int = 100, offset: int = 0) -> list[AnalysisPrompt]:
        result = await (
            self._db.table(self.TABLE)
            .select("*")
            .range(offset, offset + limit - 1)
            .order("name")
            .execute()
        )
        return [self._to_entity(row) for row in result.data]

    async def add(self, entity: AnalysisPrompt) -> AnalysisPrompt:
        data = self._to_dict(entity)
        result = await self._db.table(self.TABLE).insert(data).execute()
        return self._to_entity(result.data[0])

    async def update(self, entity: AnalysisPrompt) -> AnalysisPrompt:
        data = self._to_dict(entity)
        result = await (
            self._db.table(self.TABLE)
            .update(data)
            .eq("id", entity.id)
            .execute()
        )
        return self._to_entity(result.data[0])

    async def delete(self, id: str) -> bool:
        result = await self._db.table(self.TABLE).delete().eq("id", id).execute()
        return len(result.data) > 0

    async def count_defaults(self) -> int:
        result = await (
            self._db.table(self.TABLE)
            .select("id")
            .eq("is_default", True)
            .execute()
        )
        return len(result.data)

    def _to_entity(self, data: dict) -> AnalysisPrompt:
        return AnalysisPrompt(
            id=data["id"],
            user_id=data.get("user_id"),
            name=data["name"],
            description=data.get("description"),
            category=data["category"],
            prompt_template=data["prompt_template"],
            variables=data.get("variables") or [],
            is_default=data.get("is_default", False),
            created_at=datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")) if data.get("created_at") else datetime.now(),
            updated_at=datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00")) if data.get("updated_at") else None,
            key=data.get("key"),
            type=data.get("type", "prompt"),
        )

    def _to_dict(self, entity: AnalysisPrompt) -> dict:
        return {
            "id": entity.id,
            "user_id": entity.user_id,
            "name": entity.name,
            "description": entity.description,
            "category": entity.category,
            "prompt_template": entity.prompt_template,
            "variables": entity.variables,
            "is_default": entity.is_default,
            "created_at": entity.created_at.isoformat(),
            "updated_at": entity.updated_at.isoformat() if entity.updated_at else None,
            "key": entity.key,
            "type": entity.type,
        }
