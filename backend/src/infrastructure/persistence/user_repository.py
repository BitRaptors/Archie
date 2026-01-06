"""User repository implementation."""
from supabase import Client
from postgrest.exceptions import APIError
from domain.entities.user import User
from domain.interfaces.repositories import IUserRepository
from infrastructure.persistence.supabase_client import get_supabase_client
from datetime import datetime


class SupabaseUserRepository(IUserRepository):
    """Supabase implementation of user repository."""

    TABLE = "users"

    def __init__(self, client: Client):
        """Initialize user."""
        self._client = client

    async def get_by_id(self, id: str) -> User | None:
        """Get user by ID."""
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
            # Handle 204 No Content (no rows found)
            if e.code == "204" or "204" in str(e):
                return None
            raise

    async def get_all(self, limit: int = 100, offset: int = 0) -> list[User]:
        """Get all users."""
        result = await (
            self._client.table(self.TABLE)
            .select("*")
            .range(offset, offset + limit - 1)
            .order("created_at", desc=True)
            .execute()
        )
        return [self._to_entity(row) for row in result.data]

    async def add(self, entity: User) -> User:
        """Add user."""
        data = self._to_dict(entity)
        result = await self._client.table(self.TABLE).insert(data).execute()
        return self._to_entity(result.data[0])

    async def update(self, entity: User) -> User:
        """Update user."""
        data = self._to_dict(entity)
        result = await (
            self._client.table(self.TABLE)
            .update(data)
            .eq("id", entity.id)
            .execute()
        )
        return self._to_entity(result.data[0])

    async def delete(self, id: str) -> bool:
        """Delete user."""
        result = await self._client.table(self.TABLE).delete().eq("id", id).execute()
        return len(result.data) > 0

    def _to_entity(self, data: dict) -> User:
        """Convert database row to entity."""
        return User(
            id=data["id"],
            github_token_encrypted=data["github_token_encrypted"],
            created_at=datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")),
            updated_at=datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00")) if data.get("updated_at") else None,
        )

    def _to_dict(self, entity: User) -> dict:
        """Convert entity to database row."""
        return {
            "id": entity.id,
            "github_token_encrypted": entity.github_token_encrypted,
            "created_at": entity.created_at.isoformat(),
            "updated_at": entity.updated_at.isoformat() if entity.updated_at else None,
        }
