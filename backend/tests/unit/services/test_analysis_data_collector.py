"""Tests for AnalysisDataCollector with Supabase persistence."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime


class TestAnalysisDataCollector:
    """Tests for analysis data collector functionality."""
    
    @pytest.fixture
    def mock_supabase_client(self):
        """Create a mock Supabase client."""
        mock = AsyncMock()
        # Mock table operations
        mock_table = AsyncMock()
        mock_table.select = MagicMock(return_value=mock_table)
        mock_table.eq = MagicMock(return_value=mock_table)
        mock_table.order = MagicMock(return_value=mock_table)
        mock_table.maybe_single = MagicMock(return_value=mock_table)
        mock_table.insert = MagicMock(return_value=mock_table)
        mock_table.update = MagicMock(return_value=mock_table)
        mock_table.delete = MagicMock(return_value=mock_table)
        mock_table.execute = AsyncMock(return_value=MagicMock(data=[]))
        mock.table = MagicMock(return_value=mock_table)
        return mock
    
    @pytest.fixture
    def analysis_data_collector(self):
        """Create a fresh AnalysisDataCollector instance."""
        from application.services.analysis_data_collector import AnalysisDataCollector
        return AnalysisDataCollector()
    
    def test_initialization(self, analysis_data_collector):
        """Test that collector initializes with empty state."""
        assert analysis_data_collector._data == {}
        assert analysis_data_collector._repository is None
        assert not analysis_data_collector.is_initialized
    
    def test_initialize_with_supabase(self, analysis_data_collector, mock_supabase_client):
        """Test initialization with Supabase client."""
        analysis_data_collector.initialize(mock_supabase_client)
        
        assert analysis_data_collector.is_initialized
        assert analysis_data_collector._repository is not None
    
    @pytest.mark.asyncio
    async def test_get_data_returns_empty_when_not_initialized(self, analysis_data_collector):
        """Test get_data returns empty structure when not initialized."""
        data = await analysis_data_collector.get_data("test-analysis-id")
        
        assert data == {"gathered": {}, "phases": [], "summary": {}}
    
    @pytest.mark.asyncio
    async def test_get_data_returns_cached_data(self, analysis_data_collector):
        """Test get_data returns cached data from memory."""
        # Pre-populate cache
        analysis_data_collector._data["test-id"] = {
            "gathered": {"file_tree": {"content": "test"}},
            "phases": [{"phase": "discovery"}],
            "summary": {"phase_count": 1}
        }
        
        data = await analysis_data_collector.get_data("test-id")
        
        assert data["gathered"]["file_tree"]["content"] == "test"
        assert len(data["phases"]) == 1
    
    @pytest.mark.asyncio
    async def test_capture_gathered_data_stores_in_memory(self, analysis_data_collector):
        """Test capture_gathered_data stores data in memory."""
        await analysis_data_collector.capture_gathered_data("test-id", {
            "file_tree_raw": "src/\n  main.py",
            "dependencies_raw": "fastapi==0.100.0",
            "config_files": {"config.json": '{"key": "value"}'},
            "code_samples": {"main.py": "print('hello')"},
        })
        
        assert "test-id" in analysis_data_collector._data
        gathered = analysis_data_collector._data["test-id"]["gathered"]
        
        assert gathered["file_tree"]["char_count"] == len("src/\n  main.py")
        assert gathered["dependencies"]["char_count"] == len("fastapi==0.100.0")
        assert len(gathered["config_files"]["files"]) == 1
        assert len(gathered["code_samples"]["files"]) == 1
    
    @pytest.mark.asyncio
    async def test_capture_gathered_data_persists_to_supabase(self, analysis_data_collector, mock_supabase_client):
        """Test capture_gathered_data persists to Supabase when initialized."""
        analysis_data_collector.initialize(mock_supabase_client)
        
        await analysis_data_collector.capture_gathered_data("test-id", {
            "file_tree_raw": "src/",
            "dependencies_raw": "",
            "config_files": {},
            "code_samples": {},
        })
        
        # Verify table operations were called
        mock_supabase_client.table.assert_called()
    
    @pytest.mark.asyncio
    async def test_capture_phase_data_stores_in_memory(self, analysis_data_collector):
        """Test capture_phase_data stores phase info in memory."""
        await analysis_data_collector.capture_phase_data(
            analysis_id="test-id",
            phase_name="discovery",
            gathered={"file_tree": {"content": "tree", "char_count": 4}},
            sent={"file_tree": {"content": "tre", "char_count": 3}},
            rag_retrieved={"content": "rag data", "char_count": 8}
        )
        
        assert "test-id" in analysis_data_collector._data
        phases = analysis_data_collector._data["test-id"]["phases"]
        
        assert len(phases) == 1
        assert phases[0]["phase"] == "discovery"
        assert "timestamp" in phases[0]
        assert phases[0]["gathered"]["file_tree"]["char_count"] == 4
        assert phases[0]["sent_to_ai"]["file_tree"]["char_count"] == 3
        assert phases[0]["rag_retrieved"]["char_count"] == 8
    
    @pytest.mark.asyncio
    async def test_capture_phase_data_updates_summary(self, analysis_data_collector):
        """Test capture_phase_data updates summary metrics."""
        await analysis_data_collector.capture_phase_data(
            analysis_id="test-id",
            phase_name="discovery",
            gathered={},
            sent={"full_prompt": "This is a test prompt"},
        )
        
        summary = analysis_data_collector._data["test-id"]["summary"]
        
        assert summary["phase_count"] == 1
        assert summary["total_chars_sent"] == len("This is a test prompt")
        assert "last_updated" in summary
    
    @pytest.mark.asyncio
    async def test_capture_multiple_phases(self, analysis_data_collector):
        """Test capturing multiple phases in sequence including observation."""
        # All 7 phases in the new architecture-agnostic workflow
        phases = ["observation", "discovery", "layers", "patterns", "communication", "technology", "backend_synthesis"]
        
        for phase in phases:
            await analysis_data_collector.capture_phase_data(
                analysis_id="test-id",
                phase_name=phase,
                gathered={},
                sent={"data": {"char_count": 100}},
            )
        
        stored_phases = analysis_data_collector._data["test-id"]["phases"]
        summary = analysis_data_collector._data["test-id"]["summary"]
        
        assert len(stored_phases) == 7
        assert summary["phase_count"] == 7
        assert [p["phase"] for p in stored_phases] == phases
    
    @pytest.mark.asyncio
    async def test_capture_observation_phase_data(self, analysis_data_collector):
        """Test capturing observation phase with file signatures."""
        file_signatures = """
## src/app.py
```python
import os
from fastapi import FastAPI
class AppConfig:
    pass
```

## src/services/user_service.py
```python
from typing import Optional
from domain.user import User
class UserService:
    async def get_user(self, user_id: str) -> Optional[User]:
        pass
```
"""
        observation_prompt = f"Analyze these file signatures:\n{file_signatures}"
        
        await analysis_data_collector.capture_phase_data(
            analysis_id="test-id",
            phase_name="observation",
            gathered={"file_signatures": {"full_content": file_signatures, "char_count": len(file_signatures)}},
            sent={"file_signatures": {"content": file_signatures, "char_count": len(file_signatures)}, "full_prompt": observation_prompt},
        )
        
        phases = analysis_data_collector._data["test-id"]["phases"]
        assert len(phases) == 1
        assert phases[0]["phase"] == "observation"
        assert "file_signatures" in phases[0]["gathered"]
        assert phases[0]["gathered"]["file_signatures"]["char_count"] > 0
    
    @pytest.mark.asyncio
    async def test_capture_rag_stats_stores_in_gathered(self, analysis_data_collector):
        """Test capture_rag_stats updates gathered data."""
        await analysis_data_collector.capture_rag_stats("test-id", {
            "files": 50,
            "chunks": 200,
            "total_lines": 5000,
        })
        
        gathered = analysis_data_collector._data["test-id"]["gathered"]
        
        assert gathered["rag_indexing"]["files"] == 50
        assert gathered["rag_indexing"]["chunks"] == 200
        assert gathered["rag_indexing"]["total_lines"] == 5000
    
    def test_update_summary_calculates_total_chars(self, analysis_data_collector):
        """Test _update_summary correctly calculates total chars sent."""
        analysis_data_collector._data["test-id"] = {
            "gathered": {},
            "phases": [
                {"sent_to_ai": {"data1": {"char_count": 100}, "data2": {"char_count": 200}}},
                {"sent_to_ai": {"full_prompt": "abc"}},  # 3 chars
            ],
            "summary": {}
        }
        
        analysis_data_collector._update_summary("test-id")
        
        summary = analysis_data_collector._data["test-id"]["summary"]
        assert summary["total_chars_sent"] == 303  # 100 + 200 + 3


class TestSupabaseAnalysisDataRepository:
    """Tests for SupabaseAnalysisDataRepository."""
    
    @pytest.fixture
    def mock_supabase_client(self):
        """Create a mock Supabase client."""
        mock = AsyncMock()
        mock_table = AsyncMock()
        mock.table = MagicMock(return_value=mock_table)
        return mock, mock_table
    
    @pytest.fixture
    def repository(self, mock_supabase_client):
        """Create repository instance."""
        from infrastructure.persistence.analysis_data_repository import SupabaseAnalysisDataRepository
        client, _ = mock_supabase_client
        return SupabaseAnalysisDataRepository(client)
    
    @pytest.mark.asyncio
    async def test_get_by_analysis_id_returns_empty_list(self, repository, mock_supabase_client):
        """Test get_by_analysis_id returns empty list when no data."""
        client, mock_table = mock_supabase_client
        mock_table.select = MagicMock(return_value=mock_table)
        mock_table.eq = MagicMock(return_value=mock_table)
        mock_table.order = MagicMock(return_value=mock_table)
        mock_table.execute = AsyncMock(return_value=MagicMock(data=[]))
        
        result = await repository.get_by_analysis_id("test-id")
        
        assert result == []
        client.table.assert_called_with("analysis_data")
    
    @pytest.mark.asyncio
    async def test_get_by_analysis_id_returns_data(self, repository, mock_supabase_client):
        """Test get_by_analysis_id returns data rows."""
        client, mock_table = mock_supabase_client
        mock_table.select = MagicMock(return_value=mock_table)
        mock_table.eq = MagicMock(return_value=mock_table)
        mock_table.order = MagicMock(return_value=mock_table)
        mock_table.execute = AsyncMock(return_value=MagicMock(data=[
            {"id": "1", "analysis_id": "test-id", "data_type": "gathered", "data": {}},
            {"id": "2", "analysis_id": "test-id", "data_type": "phase_discovery", "data": {}},
        ]))
        
        result = await repository.get_by_analysis_id("test-id")
        
        assert len(result) == 2
    
    @pytest.mark.asyncio
    async def test_get_by_type_returns_none_when_not_found(self, repository, mock_supabase_client):
        """Test get_by_type returns None when no matching data."""
        client, mock_table = mock_supabase_client
        mock_table.select = MagicMock(return_value=mock_table)
        mock_table.eq = MagicMock(return_value=mock_table)
        mock_table.maybe_single = MagicMock(return_value=mock_table)
        mock_table.execute = AsyncMock(return_value=MagicMock(data=None))
        
        result = await repository.get_by_type("test-id", "gathered")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_upsert_inserts_new_entry(self, repository, mock_supabase_client):
        """Test upsert creates new entry when not exists."""
        client, mock_table = mock_supabase_client
        
        # Mock get_by_type to return None (not exists)
        mock_table.select = MagicMock(return_value=mock_table)
        mock_table.eq = MagicMock(return_value=mock_table)
        mock_table.maybe_single = MagicMock(return_value=mock_table)
        mock_table.execute = AsyncMock(return_value=MagicMock(data=None))
        
        # Mock insert
        mock_table.insert = MagicMock(return_value=mock_table)
        
        await repository.upsert("test-id", "gathered", {"key": "value"})
        
        mock_table.insert.assert_called()
    
    @pytest.mark.asyncio
    async def test_delete_by_analysis_id(self, repository, mock_supabase_client):
        """Test delete_by_analysis_id removes all entries."""
        client, mock_table = mock_supabase_client
        mock_table.delete = MagicMock(return_value=mock_table)
        mock_table.eq = MagicMock(return_value=mock_table)
        mock_table.execute = AsyncMock(return_value=MagicMock(data=[{"id": "1"}, {"id": "2"}]))
        
        result = await repository.delete_by_analysis_id("test-id")
        
        assert result == 2
        mock_table.delete.assert_called()


class TestAnalysisDataCollectorIntegration:
    """Integration tests for analysis data collector with Supabase."""
    
    @pytest.fixture
    def mock_repository(self):
        """Create a mock analysis data repository."""
        mock = AsyncMock()
        mock.get_by_analysis_id = AsyncMock(return_value=[])
        mock.get_by_type = AsyncMock(return_value=None)
        mock.upsert = AsyncMock(return_value={"id": "new-id"})
        return mock
    
    @pytest.mark.asyncio
    async def test_full_analysis_flow(self, mock_repository):
        """Test complete analysis data flow with observation-first architecture."""
        from application.services.analysis_data_collector import AnalysisDataCollector
        
        collector = AnalysisDataCollector()
        collector._repository = mock_repository
        collector._initialized = True
        
        analysis_id = "integration-test-id"
        
        # Step 1: Capture gathered data
        await collector.capture_gathered_data(analysis_id, {
            "file_tree_raw": "src/\n  app.py\n  utils/\n    helper.py",
            "dependencies_raw": "fastapi==0.100.0\npydantic==2.0.0",
            "config_files": {"pyproject.toml": "[project]\nname='test'"},
            "code_samples": {"app.py": "from fastapi import FastAPI\napp = FastAPI()"},
        })
        
        # Step 2: Capture phase data for all 7 phases (including observation)
        phases = [
            ("observation", "File signatures show a FastAPI app with layered structure"),
            ("discovery", "Discovered a FastAPI application with utils module"),
            ("layers", "Found presentation layer (app.py) and utility layer (utils/)"),
            ("patterns", "Repository pattern not used, simple module structure"),
            ("communication", "HTTP endpoints via FastAPI"),
            ("technology", "Python 3.x, FastAPI, Pydantic"),
            ("backend_synthesis", "Complete backend architecture analysis"),
        ]
        
        for phase_name, description in phases:
            await collector.capture_phase_data(
                analysis_id=analysis_id,
                phase_name=phase_name,
                gathered={"description": description},
                sent={"full_prompt": f"Analyze {phase_name}: {description}"},
            )
        
        # Verify final state
        data = await collector.get_data(analysis_id)
        
        assert len(data["phases"]) == 7
        assert data["summary"]["phase_count"] == 7
        assert data["gathered"]["file_tree"]["char_count"] > 0
        
        # Verify observation is first phase
        assert data["phases"][0]["phase"] == "observation"
        
        # Verify repository was called for persistence
        assert mock_repository.upsert.call_count >= 8  # 1 gathered + 7 phases
