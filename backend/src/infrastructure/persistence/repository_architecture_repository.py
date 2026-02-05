"""Repository architecture repository implementation for learned architecture."""
from supabase import Client
from postgrest.exceptions import APIError
from datetime import datetime, timezone
from domain.entities.architecture_rule import ArchitectureRule
from domain.interfaces.repositories import IRepositoryArchitectureRepository


class SupabaseRepositoryArchitectureRepository(IRepositoryArchitectureRepository):
    """Supabase implementation of repository architecture repository (learned architecture)."""

    TABLE = "repository_architecture"

    def __init__(self, client: Client):
        """Initialize repository."""
        self._client = client

    async def get_by_id(self, id: str) -> ArchitectureRule | None:
        """Get a rule by its ID."""
        try:
            result = await (
                self._client.table(self.TABLE)
                .select("*")
                .eq("id", id)
                .maybe_single()
                .execute()
            )
            if result and result.data:
                return self._to_entity(result.data)
            return None
        except APIError as e:
            if e.code == "204" or "204" in str(e):
                return None
            raise

    async def get_by_repository_id(self, repository_id: str) -> list[ArchitectureRule]:
        """Get all learned rules for a repository."""
        result = await (
            self._client.table(self.TABLE)
            .select("*")
            .eq("repository_id", repository_id)
            .order("rule_type")
            .order("rule_id")
            .execute()
        )
        return [self._to_entity(row) for row in result.data]

    async def get_by_repository_and_type(self, repository_id: str, rule_type: str) -> list[ArchitectureRule]:
        """Get learned rules for a repository filtered by type."""
        result = await (
            self._client.table(self.TABLE)
            .select("*")
            .eq("repository_id", repository_id)
            .eq("rule_type", rule_type)
            .order("rule_id")
            .execute()
        )
        return [self._to_entity(row) for row in result.data]

    async def get_by_analysis_id(self, analysis_id: str) -> list[ArchitectureRule]:
        """Get all rules extracted in a specific analysis."""
        result = await (
            self._client.table(self.TABLE)
            .select("*")
            .eq("analysis_id", analysis_id)
            .order("rule_type")
            .order("rule_id")
            .execute()
        )
        return [self._to_entity(row) for row in result.data]

    async def add(self, rule: ArchitectureRule) -> ArchitectureRule:
        """Add a new learned rule."""
        data = self._to_dict(rule)
        result = await self._client.table(self.TABLE).insert(data).execute()
        return self._to_entity(result.data[0])

    async def add_many(self, rules: list[ArchitectureRule]) -> list[ArchitectureRule]:
        """Add multiple learned rules."""
        if not rules:
            return []
        
        data_list = [self._to_dict(rule) for rule in rules]
        result = await self._client.table(self.TABLE).insert(data_list).execute()
        return [self._to_entity(row) for row in result.data]

    async def update(self, rule: ArchitectureRule) -> ArchitectureRule:
        """Update an existing rule."""
        data = self._to_dict(rule)
        data["updated_at"] = datetime.now(timezone.utc).isoformat()
        result = await (
            self._client.table(self.TABLE)
            .update(data)
            .eq("id", rule.id)
            .execute()
        )
        return self._to_entity(result.data[0])

    async def delete(self, id: str) -> bool:
        """Delete a rule by ID."""
        result = await self._client.table(self.TABLE).delete().eq("id", id).execute()
        return len(result.data) > 0

    async def delete_by_repository_id(self, repository_id: str) -> int:
        """Delete all rules for a repository. Returns count deleted."""
        result = await (
            self._client.table(self.TABLE)
            .delete()
            .eq("repository_id", repository_id)
            .execute()
        )
        return len(result.data)

    def _to_entity(self, data: dict) -> ArchitectureRule:
        """Convert database row to entity."""
        created_at = None
        if data.get("created_at"):
            created_at = datetime.fromisoformat(data["created_at"].replace("Z", "+00:00"))
        
        updated_at = None
        if data.get("updated_at"):
            updated_at = datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00"))
        
        source_files = data.get("source_files")
        if source_files and isinstance(source_files, str):
            import json
            source_files = json.loads(source_files)
        
        return ArchitectureRule(
            id=data["id"],
            repository_id=data["repository_id"],
            analysis_id=data.get("analysis_id"),
            rule_type=data["rule_type"],
            rule_id=data["rule_id"],
            name=data["name"],
            description=data.get("description"),
            rule_data=data["rule_data"],
            confidence=data.get("confidence", 1.0),
            source_files=source_files,
            created_at=created_at,
            updated_at=updated_at,
        )

    def _to_dict(self, entity: ArchitectureRule) -> dict:
        """Convert entity to database row."""
        return {
            "id": entity.id,
            "repository_id": entity.repository_id,
            "analysis_id": entity.analysis_id,
            "rule_type": entity.rule_type,
            "rule_id": entity.rule_id,
            "name": entity.name,
            "description": entity.description,
            "rule_data": entity.rule_data,
            "confidence": entity.confidence,
            "source_files": entity.source_files,
            "created_at": entity.created_at.isoformat() if entity.created_at else datetime.now(timezone.utc).isoformat(),
            "updated_at": entity.updated_at.isoformat() if entity.updated_at else None,
        }
