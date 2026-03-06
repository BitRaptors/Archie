"""Analysis repository implementation."""
from domain.entities.analysis import Analysis
from domain.interfaces.database import DatabaseClient, DatabaseError
from domain.interfaces.repositories import IRepository
from datetime import datetime


class AnalysisRepository(IRepository[Analysis, str]):
    """Analysis repository."""

    TABLE = "analyses"

    def __init__(self, db: DatabaseClient):
        self._db = db

    async def get_by_id(self, id: str) -> Analysis | None:
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

    async def get_all(self, limit: int = 100, offset: int = 0) -> list[Analysis]:
        result = await (
            self._db.table(self.TABLE)
            .select("*")
            .range(offset, offset + limit - 1)
            .order("created_at", desc=True)
            .execute()
        )
        return [self._to_entity(row) for row in result.data]

    async def get_latest_by_repo_id(self, repository_id: str) -> Analysis | None:
        """Get the latest analysis for a given repository ID."""
        try:
            result = await (
                self._db.table(self.TABLE)
                .select("*")
                .eq("repository_id", repository_id)
                .order("created_at", desc=True)
                .limit(1)
                .maybe_single()
                .execute()
            )
            if result and result.data:
                return self._to_entity(result.data)
            return None
        except Exception:
            return None

    async def add(self, entity: Analysis) -> Analysis:
        data = self._to_dict(entity)
        result = await self._db.table(self.TABLE).insert(data).execute()
        return self._to_entity(result.data[0])

    async def update(self, entity: Analysis) -> Analysis:
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

    def _to_entity(self, data: dict) -> Analysis:
        return Analysis(
            id=data["id"],
            repository_id=data["repository_id"],
            status=data["status"],
            progress_percentage=data["progress_percentage"],
            error_message=data.get("error_message"),
            started_at=datetime.fromisoformat(data["started_at"].replace("Z", "+00:00")) if data.get("started_at") else None,
            completed_at=datetime.fromisoformat(data["completed_at"].replace("Z", "+00:00")) if data.get("completed_at") else None,
            created_at=datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")),
            commit_sha=data.get("commit_sha"),
        )

    def _to_dict(self, entity: Analysis) -> dict:
        return {
            "id": entity.id,
            "repository_id": entity.repository_id,
            "status": entity.status,
            "progress_percentage": entity.progress_percentage,
            "error_message": entity.error_message,
            "started_at": entity.started_at.isoformat() if entity.started_at else None,
            "completed_at": entity.completed_at.isoformat() if entity.completed_at else None,
            "created_at": entity.created_at.isoformat(),
            "commit_sha": entity.commit_sha,
        }
