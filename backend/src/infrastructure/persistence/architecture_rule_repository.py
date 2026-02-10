"""Architecture rule repository implementation for reference architecture."""
from datetime import datetime, timezone
from domain.entities.architecture_rule import ArchitectureRule
from domain.interfaces.database import DatabaseClient, DatabaseError
from domain.interfaces.repositories import IArchitectureRuleRepository


class ArchitectureRuleRepository(IArchitectureRuleRepository):
    """Architecture rule repository (reference architecture)."""

    TABLE = "architecture_rules"

    def __init__(self, db: DatabaseClient):
        self._db = db

    async def get_by_id(self, id: str) -> ArchitectureRule | None:
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

    async def get_by_blueprint_id(self, blueprint_id: str) -> list[ArchitectureRule]:
        result = await (
            self._db.table(self.TABLE)
            .select("*")
            .eq("blueprint_id", blueprint_id)
            .order("rule_type")
            .order("rule_id")
            .execute()
        )
        return [self._to_entity(row) for row in result.data]

    async def get_by_blueprint_and_type(self, blueprint_id: str, rule_type: str) -> list[ArchitectureRule]:
        result = await (
            self._db.table(self.TABLE)
            .select("*")
            .eq("blueprint_id", blueprint_id)
            .eq("rule_type", rule_type)
            .order("rule_id")
            .execute()
        )
        return [self._to_entity(row) for row in result.data]

    async def get_by_rule_id(self, blueprint_id: str, rule_id: str) -> ArchitectureRule | None:
        try:
            result = await (
                self._db.table(self.TABLE)
                .select("*")
                .eq("blueprint_id", blueprint_id)
                .eq("rule_id", rule_id)
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

    async def add(self, rule: ArchitectureRule) -> ArchitectureRule:
        data = self._to_dict(rule)
        result = await self._db.table(self.TABLE).insert(data).execute()
        return self._to_entity(result.data[0])

    async def update(self, rule: ArchitectureRule) -> ArchitectureRule:
        data = self._to_dict(rule)
        data["updated_at"] = datetime.now(timezone.utc).isoformat()
        result = await (
            self._db.table(self.TABLE)
            .update(data)
            .eq("id", rule.id)
            .execute()
        )
        return self._to_entity(result.data[0])

    async def delete(self, id: str) -> bool:
        result = await self._db.table(self.TABLE).delete().eq("id", id).execute()
        return len(result.data) > 0

    async def delete_by_blueprint_id(self, blueprint_id: str) -> int:
        result = await (
            self._db.table(self.TABLE)
            .delete()
            .eq("blueprint_id", blueprint_id)
            .execute()
        )
        return len(result.data)

    async def list_blueprints(self) -> list[str]:
        result = await (
            self._db.table(self.TABLE)
            .select("blueprint_id")
            .execute()
        )
        blueprint_ids = set(row["blueprint_id"] for row in result.data)
        return sorted(list(blueprint_ids))

    def _to_entity(self, data: dict) -> ArchitectureRule:
        created_at = None
        if data.get("created_at"):
            created_at = datetime.fromisoformat(data["created_at"].replace("Z", "+00:00"))
        updated_at = None
        if data.get("updated_at"):
            updated_at = datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00"))
        return ArchitectureRule(
            id=data["id"],
            blueprint_id=data["blueprint_id"],
            rule_type=data["rule_type"],
            rule_id=data["rule_id"],
            name=data["name"],
            description=data.get("description"),
            rule_data=data["rule_data"],
            examples=data.get("examples"),
            confidence=1.0,
            created_at=created_at,
            updated_at=updated_at,
        )

    def _to_dict(self, entity: ArchitectureRule) -> dict:
        return {
            "id": entity.id,
            "blueprint_id": entity.blueprint_id,
            "rule_type": entity.rule_type,
            "rule_id": entity.rule_id,
            "name": entity.name,
            "description": entity.description,
            "rule_data": entity.rule_data,
            "examples": entity.examples,
            "created_at": entity.created_at.isoformat() if entity.created_at else datetime.now(timezone.utc).isoformat(),
            "updated_at": entity.updated_at.isoformat() if entity.updated_at else None,
        }
