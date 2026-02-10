"""Repository architecture config repository implementation."""
from datetime import datetime, timezone
from domain.entities.architecture_rule import RepositoryArchitectureConfig
from domain.interfaces.database import DatabaseClient, DatabaseError
from domain.interfaces.repositories import IRepositoryArchitectureConfigRepository


class RepositoryArchitectureConfigRepository(IRepositoryArchitectureConfigRepository):
    """Repository architecture config repository."""

    TABLE = "repository_architecture_config"

    def __init__(self, db: DatabaseClient):
        self._db = db

    async def get_by_repository_id(self, repository_id: str) -> RepositoryArchitectureConfig | None:
        try:
            result = await (
                self._db.table(self.TABLE)
                .select("*")
                .eq("repository_id", repository_id)
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

    async def add(self, config: RepositoryArchitectureConfig) -> RepositoryArchitectureConfig:
        data = self._to_dict(config)
        result = await self._db.table(self.TABLE).insert(data).execute()
        return self._to_entity(result.data[0])

    async def update(self, config: RepositoryArchitectureConfig) -> RepositoryArchitectureConfig:
        data = self._to_dict(config)
        data["updated_at"] = datetime.now(timezone.utc).isoformat()
        result = await (
            self._db.table(self.TABLE)
            .update(data)
            .eq("repository_id", config.repository_id)
            .execute()
        )
        return self._to_entity(result.data[0])

    async def upsert(self, config: RepositoryArchitectureConfig) -> RepositoryArchitectureConfig:
        data = self._to_dict(config)
        result = await (
            self._db.table(self.TABLE)
            .upsert(data, on_conflict="repository_id")
            .execute()
        )
        return self._to_entity(result.data[0])

    async def delete(self, repository_id: str) -> bool:
        result = await (
            self._db.table(self.TABLE)
            .delete()
            .eq("repository_id", repository_id)
            .execute()
        )
        return len(result.data) > 0

    def _to_entity(self, data: dict) -> RepositoryArchitectureConfig:
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
        return {
            "id": entity.id,
            "repository_id": entity.repository_id,
            "reference_blueprint_id": entity.reference_blueprint_id,
            "use_learned_architecture": entity.use_learned_architecture,
            "merge_strategy": entity.merge_strategy,
            "created_at": entity.created_at.isoformat() if entity.created_at else datetime.now(timezone.utc).isoformat(),
            "updated_at": entity.updated_at.isoformat() if entity.updated_at else None,
        }
