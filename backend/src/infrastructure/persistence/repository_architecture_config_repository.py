"""Repository architecture config repository implementation."""
from supabase import Client
from postgrest.exceptions import APIError
from datetime import datetime, timezone
from domain.entities.architecture_rule import RepositoryArchitectureConfig
from domain.interfaces.repositories import IRepositoryArchitectureConfigRepository


class SupabaseRepositoryArchitectureConfigRepository(IRepositoryArchitectureConfigRepository):
    """Supabase implementation of repository architecture config repository."""

    TABLE = "repository_architecture_config"

    def __init__(self, client: Client):
        """Initialize repository."""
        self._client = client

    async def get_by_repository_id(self, repository_id: str) -> RepositoryArchitectureConfig | None:
        """Get config for a repository."""
        try:
            result = await (
                self._client.table(self.TABLE)
                .select("*")
                .eq("repository_id", repository_id)
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

    async def add(self, config: RepositoryArchitectureConfig) -> RepositoryArchitectureConfig:
        """Add a new config."""
        data = self._to_dict(config)
        result = await self._client.table(self.TABLE).insert(data).execute()
        return self._to_entity(result.data[0])

    async def update(self, config: RepositoryArchitectureConfig) -> RepositoryArchitectureConfig:
        """Update an existing config."""
        data = self._to_dict(config)
        data["updated_at"] = datetime.now(timezone.utc).isoformat()
        result = await (
            self._client.table(self.TABLE)
            .update(data)
            .eq("repository_id", config.repository_id)
            .execute()
        )
        return self._to_entity(result.data[0])

    async def upsert(self, config: RepositoryArchitectureConfig) -> RepositoryArchitectureConfig:
        """Insert or update a config."""
        data = self._to_dict(config)
        result = await (
            self._client.table(self.TABLE)
            .upsert(data, on_conflict="repository_id")
            .execute()
        )
        return self._to_entity(result.data[0])

    async def delete(self, repository_id: str) -> bool:
        """Delete config for a repository."""
        result = await (
            self._client.table(self.TABLE)
            .delete()
            .eq("repository_id", repository_id)
            .execute()
        )
        return len(result.data) > 0

    def _to_entity(self, data: dict) -> RepositoryArchitectureConfig:
        """Convert database row to entity."""
        created_at = None
        if data.get("created_at"):
            created_at = datetime.fromisoformat(data["created_at"].replace("Z", "+00:00"))
        
        updated_at = None
        if data.get("updated_at"):
            updated_at = datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00"))
        
        return RepositoryArchitectureConfig(
            id=data["id"],
            repository_id=data["repository_id"],
            reference_blueprint_id=data.get("reference_blueprint_id"),
            use_learned_architecture=data.get("use_learned_architecture", True),
            merge_strategy=data.get("merge_strategy", "learned_primary"),
            created_at=created_at,
            updated_at=updated_at,
        )

    def _to_dict(self, entity: RepositoryArchitectureConfig) -> dict:
        """Convert entity to database row."""
        return {
            "id": entity.id,
            "repository_id": entity.repository_id,
            "reference_blueprint_id": entity.reference_blueprint_id,
            "use_learned_architecture": entity.use_learned_architecture,
            "merge_strategy": entity.merge_strategy,
            "created_at": entity.created_at.isoformat() if entity.created_at else datetime.now(timezone.utc).isoformat(),
            "updated_at": entity.updated_at.isoformat() if entity.updated_at else None,
        }
