"""Repository repository implementation."""
from domain.entities.repository import Repository
from domain.interfaces.database import DatabaseClient, DatabaseError
from domain.interfaces.repositories import IRepositoryRepository
from datetime import datetime


class RepositoryRepository(IRepositoryRepository):
    """Repository repository."""

    TABLE = "repositories"

    def __init__(self, db: DatabaseClient):
        self._db = db

    async def get_by_id(self, id: str) -> Repository | None:
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

    async def get_all(self, limit: int = 100, offset: int = 0) -> list[Repository]:
        result = await (
            self._db.table(self.TABLE)
            .select("*")
            .range(offset, offset + limit - 1)
            .order("created_at", desc=True)
            .execute()
        )
        return [self._to_entity(row) for row in result.data]

    async def get_by_user_id(self, user_id: str, limit: int = 100, offset: int = 0) -> list[Repository]:
        result = await (
            self._db.table(self.TABLE)
            .select("*")
            .eq("user_id", user_id)
            .range(offset, offset + limit - 1)
            .order("created_at", desc=True)
            .execute()
        )
        return [self._to_entity(row) for row in result.data]

    async def get_by_full_name(self, user_id: str, owner: str, name: str) -> Repository | None:
        try:
            result = await (
                self._db.table(self.TABLE)
                .select("*")
                .eq("user_id", user_id)
                .eq("owner", owner)
                .eq("name", name)
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

    async def add(self, entity: Repository) -> Repository:
        data = self._to_dict(entity)
        result = await self._db.table(self.TABLE).insert(data).execute()
        return self._to_entity(result.data[0])

    async def update(self, entity: Repository) -> Repository:
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

    def _to_entity(self, data: dict) -> Repository:
        return Repository(
            id=data["id"],
            user_id=data["user_id"],
            owner=data["owner"],
            name=data["name"],
            full_name=data["full_name"],
            url=data["url"],
            description=data.get("description"),
            language=data.get("language"),
            default_branch=data.get("default_branch", "main"),
            created_at=datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")),
            updated_at=datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00")) if data.get("updated_at") else None,
        )

    def _to_dict(self, entity: Repository) -> dict:
        return {
            "id": entity.id,
            "user_id": entity.user_id,
            "owner": entity.owner,
            "name": entity.name,
            "full_name": entity.full_name,
            "url": entity.url,
            "description": entity.description,
            "language": entity.language,
            "default_branch": entity.default_branch,
            "created_at": entity.created_at.isoformat(),
            "updated_at": entity.updated_at.isoformat() if entity.updated_at else None,
        }
