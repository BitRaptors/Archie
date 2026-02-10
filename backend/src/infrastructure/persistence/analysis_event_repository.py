"""Analysis event repository implementation."""
from domain.entities.analysis_event import AnalysisEvent
from domain.interfaces.database import DatabaseClient, DatabaseError
from domain.interfaces.repositories import IAnalysisEventRepository
from datetime import datetime


class AnalysisEventRepository(IAnalysisEventRepository):
    """Analysis event repository."""

    TABLE = "analysis_events"

    def __init__(self, db: DatabaseClient):
        self._db = db

    async def get_by_id(self, id: str) -> AnalysisEvent | None:
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

    async def get_all(self, limit: int = 100, offset: int = 0) -> list[AnalysisEvent]:
        result = await (
            self._db.table(self.TABLE)
            .select("*")
            .range(offset, offset + limit - 1)
            .order("created_at", desc=False)
            .execute()
        )
        return [self._to_entity(row) for row in result.data]

    async def get_by_analysis_id(self, analysis_id: str) -> list[AnalysisEvent]:
        result = await (
            self._db.table(self.TABLE)
            .select("*")
            .eq("analysis_id", analysis_id)
            .order("created_at", desc=False)
            .execute()
        )
        return [self._to_entity(row) for row in result.data]

    async def add(self, entity: AnalysisEvent) -> AnalysisEvent:
        data = self._to_dict(entity)
        result = await self._db.table(self.TABLE).insert(data).execute()
        return self._to_entity(result.data[0])

    async def update(self, entity: AnalysisEvent) -> AnalysisEvent:
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

    def _to_entity(self, data: dict) -> AnalysisEvent:
        return AnalysisEvent(
            id=data["id"],
            analysis_id=data["analysis_id"],
            event_type=data["event_type"],
            message=data["message"],
            details=data.get("details"),
            created_at=datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")),
        )

    def _to_dict(self, entity: AnalysisEvent) -> dict:
        return {
            "id": entity.id,
            "analysis_id": entity.analysis_id,
            "event_type": entity.event_type,
            "message": entity.message,
            "details": entity.details,
            "created_at": entity.created_at.isoformat(),
        }
