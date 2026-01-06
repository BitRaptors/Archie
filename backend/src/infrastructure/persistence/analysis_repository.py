"""Analysis repository implementation."""
from supabase import Client
from postgrest.exceptions import APIError
from domain.entities.analysis import Analysis
from domain.interfaces.repositories import IRepository
from datetime import datetime


class SupabaseAnalysisRepository(IRepository[Analysis, str]):
    """Supabase implementation of analysis repository."""

    TABLE = "analyses"

    def __init__(self, client: Client):
        """Initialize analysis."""
        self._client = client

    async def get_by_id(self, id: str) -> Analysis | None:
        """Get analysis by ID."""
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

    async def get_all(self, limit: int = 100, offset: int = 0) -> list[Analysis]:
        """Get all analyses."""
        result = await (
            self._client.table(self.TABLE)
            .select("*")
            .range(offset, offset + limit - 1)
            .order("created_at", desc=True)
            .execute()
        )
        return [self._to_entity(row) for row in result.data]

    async def add(self, entity: Analysis) -> Analysis:
        """Add analysis."""
        data = self._to_dict(entity)
        result = await self._client.table(self.TABLE).insert(data).execute()
        return self._to_entity(result.data[0])

    async def update(self, entity: Analysis) -> Analysis:
        """Update analysis."""
        data = self._to_dict(entity)
        result = await (
            self._client.table(self.TABLE)
            .update(data)
            .eq("id", entity.id)
            .execute()
        )
        return self._to_entity(result.data[0])

    async def delete(self, id: str) -> bool:
        """Delete analysis."""
        result = await self._client.table(self.TABLE).delete().eq("id", id).execute()
        return len(result.data) > 0

    def _to_entity(self, data: dict) -> Analysis:
        """Convert database row to entity."""
        return Analysis(
            id=data["id"],
            repository_id=data["repository_id"],
            status=data["status"],
            progress_percentage=data["progress_percentage"],
            error_message=data.get("error_message"),
            started_at=datetime.fromisoformat(data["started_at"].replace("Z", "+00:00")) if data.get("started_at") else None,
            completed_at=datetime.fromisoformat(data["completed_at"].replace("Z", "+00:00")) if data.get("completed_at") else None,
            created_at=datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")),
        )

    def _to_dict(self, entity: Analysis) -> dict:
        """Convert entity to database row."""
        return {
            "id": entity.id,
            "repository_id": entity.repository_id,
            "status": entity.status,
            "progress_percentage": entity.progress_percentage,
            "error_message": entity.error_message,
            "started_at": entity.started_at.isoformat() if entity.started_at else None,
            "completed_at": entity.completed_at.isoformat() if entity.completed_at else None,
            "created_at": entity.created_at.isoformat(),
        }
