"""User profile repository implementation."""
import uuid
from datetime import datetime, timezone

from domain.entities.user_profile import UserProfile
from domain.interfaces.database import DatabaseClient, DatabaseError
from domain.interfaces.repositories import IUserProfileRepository

# Deterministic default user ID — matches the one used in repositories.py route
_DEFAULT_USER_ID = str(uuid.uuid5(uuid.NAMESPACE_DNS, "default-user"))


class UserProfileRepository(IUserProfileRepository):
    """User profile repository.

    Manages the single-row user_profiles table.
    """

    TABLE = "user_profiles"

    def __init__(self, db: DatabaseClient):
        self._db = db

    async def get_default(self) -> UserProfile | None:
        """Get the default (single) user profile."""
        try:
            result = await (
                self._db.table(self.TABLE)
                .select("*")
                .limit(1)
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

    async def upsert(self, profile: UserProfile) -> UserProfile:
        """Insert or update a user profile."""
        data = self._to_dict(profile)
        data["updated_at"] = datetime.now(timezone.utc).isoformat()
        result = await (
            self._db.table(self.TABLE)
            .upsert(data, on_conflict="id")
            .execute()
        )
        return self._to_entity(result.data[0])

    async def set_active_repo(self, repo_id: str | None) -> None:
        """Set (or clear) the active repository.

        If no profile row exists yet, creates one.
        """
        profile = await self.get_default()
        now = datetime.now(timezone.utc).isoformat()

        if profile:
            await (
                self._db.table(self.TABLE)
                .update({"active_repository_id": repo_id, "updated_at": now})
                .eq("id", profile.id)
                .execute()
            )
        else:
            # Create a new profile row
            await (
                self._db.table(self.TABLE)
                .insert({"user_id": _DEFAULT_USER_ID, "active_repository_id": repo_id, "updated_at": now})
                .execute()
            )

    # -- mapping helpers -------------------------------------------------------

    def _to_entity(self, data: dict) -> UserProfile:
        created_at = None
        if data.get("created_at"):
            created_at = datetime.fromisoformat(
                data["created_at"].replace("Z", "+00:00")
            )
        updated_at = None
        if data.get("updated_at"):
            updated_at = datetime.fromisoformat(
                data["updated_at"].replace("Z", "+00:00")
            )
        return UserProfile(
            id=data["id"],
            active_repo_id=data.get("active_repository_id"),
            preferences=data.get("preferences") or {},
            created_at=created_at,
            updated_at=updated_at,
        )

    def _to_dict(self, entity: UserProfile) -> dict:
        d: dict = {
            "user_id": _DEFAULT_USER_ID,
            "active_repository_id": entity.active_repo_id,
            "preferences": entity.preferences,
        }
        if entity.id:
            d["id"] = entity.id
        if entity.created_at:
            d["created_at"] = entity.created_at.isoformat()
        if entity.updated_at:
            d["updated_at"] = entity.updated_at.isoformat()
        return d
