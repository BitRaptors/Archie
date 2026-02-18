"""Repositories for discovery_ignored_dirs and library_capabilities tables."""
from datetime import datetime

from domain.entities.analysis_settings import IgnoredDirectory, LibraryCapability
from domain.interfaces.database import DatabaseClient


class IgnoredDirsRepository:
    """CRUD repository for discovery_ignored_dirs."""

    TABLE = "discovery_ignored_dirs"

    def __init__(self, db: DatabaseClient):
        self._db = db

    async def get_all(self) -> list[IgnoredDirectory]:
        result = await (
            self._db.table(self.TABLE)
            .select("*")
            .order("directory_name")
            .execute()
        )
        return [self._to_entity(row) for row in result.data]

    async def replace_all(self, directory_names: list[str]) -> list[IgnoredDirectory]:
        """Replace all rows with the given list of directory names."""
        # Delete all existing
        await self._db.table(self.TABLE).delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
        # Insert new
        if directory_names:
            rows = [{"directory_name": name} for name in directory_names]
            await self._db.table(self.TABLE).insert(rows).execute()
        return await self.get_all()

    def _to_entity(self, data: dict) -> IgnoredDirectory:
        return IgnoredDirectory(
            id=data["id"],
            directory_name=data["directory_name"],
            created_at=datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")) if data.get("created_at") else None,
        )


class LibraryCapabilitiesRepository:
    """CRUD repository for library_capabilities."""

    TABLE = "library_capabilities"

    def __init__(self, db: DatabaseClient):
        self._db = db

    async def get_all(self) -> list[LibraryCapability]:
        result = await (
            self._db.table(self.TABLE)
            .select("*")
            .order("library_name")
            .execute()
        )
        return [self._to_entity(row) for row in result.data]

    async def replace_all(self, libraries: list[dict]) -> list[LibraryCapability]:
        """Replace all rows. Each dict: {library_name, ecosystem, capabilities}."""
        # Delete all existing
        await self._db.table(self.TABLE).delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
        # Insert new
        if libraries:
            rows = [
                {
                    "library_name": lib["library_name"],
                    "ecosystem": lib.get("ecosystem", ""),
                    "capabilities": lib.get("capabilities", []),
                }
                for lib in libraries
            ]
            await self._db.table(self.TABLE).insert(rows).execute()
        return await self.get_all()

    def _to_entity(self, data: dict) -> LibraryCapability:
        caps = data.get("capabilities", [])
        # Handle Postgres text[] returned as list or string
        if isinstance(caps, str):
            caps = [c.strip() for c in caps.strip("{}").split(",") if c.strip()]

        return LibraryCapability(
            id=data["id"],
            library_name=data["library_name"],
            ecosystem=data.get("ecosystem", ""),
            capabilities=caps,
            created_at=datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")) if data.get("created_at") else None,
            updated_at=datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00")) if data.get("updated_at") else None,
        )
