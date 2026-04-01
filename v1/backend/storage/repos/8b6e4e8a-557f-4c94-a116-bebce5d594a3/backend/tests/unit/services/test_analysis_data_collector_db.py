"""Tests for AnalysisDataCollector with DatabaseClient.

Verifies:
  - initialize() accepts a DatabaseClient directly (no SupabaseAdapter wrapping)
  - No more import of SupabaseAdapter inside the collector
  - save/load round-trip works
"""
import pytest
from unittest.mock import MagicMock

from domain.interfaces.database import DatabaseClient, QueryBuilder, QueryResult


class MockQueryBuilder(QueryBuilder):
    def __init__(self):
        for method in ("select", "insert", "update", "delete", "upsert",
                       "eq", "in_", "range", "order", "limit", "maybe_single"):
            pass

    def select(self, columns="*"): return self
    def insert(self, data): return self
    def update(self, data): return self
    def delete(self): return self
    def upsert(self, data, *, on_conflict=""): return self
    def eq(self, column, value): return self
    def in_(self, column, values): return self
    def range(self, start, end): return self
    def order(self, column, *, desc=False): return self
    def limit(self, count): return self
    def maybe_single(self): return self

    async def execute(self):
        return QueryResult(data=[])


class MockDB(DatabaseClient):
    def table(self, name: str) -> QueryBuilder:
        return MockQueryBuilder()


class TestAnalysisDataCollectorDB:

    def test_initialize_with_db_client(self):
        from application.services.analysis_data_collector import AnalysisDataCollector

        collector = AnalysisDataCollector()
        db = MockDB()
        collector.initialize(db)
        assert collector.is_initialized
        assert collector._repository is not None

    def test_initialize_replaces_supabase_adapter(self):
        """Verify the collector module no longer imports SupabaseAdapter."""
        import application.services.analysis_data_collector as mod
        source = open(mod.__file__).read()
        assert "from infrastructure.persistence.supabase_adapter import" not in source
        assert "SupabaseAdapter(" not in source

    @pytest.mark.asyncio
    async def test_save_and_load_roundtrip(self):
        """capture_phase_data → get_data returns same data (in-memory path)."""
        from application.services.analysis_data_collector import AnalysisDataCollector

        collector = AnalysisDataCollector()
        # Don't initialize (no DB) — uses in-memory only
        await collector.capture_phase_data(
            analysis_id="test-123",
            phase_name="discovery",
            gathered={"file_tree": "..."},
            sent={"full_prompt": "analyze..."},
            output="result",
        )
        data = await collector.get_data("test-123")
        assert len(data["phases"]) == 1
        assert data["phases"][0]["phase"] == "discovery"
        assert data["phases"][0]["output"] == "result"
