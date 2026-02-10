"""User repository implementation."""
from domain.entities.user import User
from domain.interfaces.database import DatabaseClient, DatabaseError
from domain.interfaces.repositories import IUserRepository
from datetime import datetime


class UserRepository(IUserRepository):
    """User repository."""

    TABLE = "users"

    def __init__(self, db: DatabaseClient):
        self._db = db

    async def get_by_id(self, id: str) -> User | None:
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

    async def get_all(self, limit: int = 100, offset: int = 0) -> list[User]:
        result = await (
            self._db.table(self.TABLE)
            .select("*")
            .range(offset, offset + limit - 1)
            .order("created_at", desc=True)
            .execute()
        )
        return [self._to_entity(row) for row in result.data]

    async def add(self, entity: User) -> User:
        data = self._to_dict(entity)
        result = await self._db.table(self.TABLE).insert(data).execute()
        return self._to_entity(result.data[0])

    async def update(self, entity: User) -> User:
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

    def _to_entity(self, data: dict) -> User:
        return User(
            id=data["id"],
            github_token_encrypted=data["github_token_encrypted"],
            created_at=datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")),
            updated_at=datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00")) if data.get("updated_at") else None,
        )

    def _to_dict(self, entity: User) -> dict:
        return {
            "id": entity.id,
            "github_token_encrypted": entity.github_token_encrypted,
            "created_at": entity.created_at.isoformat(),
            "updated_at": entity.updated_at.isoformat() if entity.updated_at else None,
        }
