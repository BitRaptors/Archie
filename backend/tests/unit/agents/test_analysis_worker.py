"""Tests for AnalysisWorker."""
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock


class TestAnalysisWorker:
    """Tests for analysis worker functionality."""
    
    @pytest.fixture
    def worker(self, mock_ai_client, mock_prompt_loader):
        """Create analysis worker instance."""
        from application.agents.analysis_worker import AnalysisWorker
        return AnalysisWorker(
            ai_client=mock_ai_client,
            prompt_loader=mock_prompt_loader,
        )
    
    @pytest.fixture
    def assignment(self):
        """Create sample assignment."""
        from domain.entities.worker_assignment import WorkerAssignment
        return WorkerAssignment.create_analysis_assignment(
            files=["src/handlers/user.py", "src/services/user_service.py"],
            token_budget=150_000,
        )
    
    @pytest.mark.asyncio
    async def test_execute_reads_files(self, worker, assignment, sample_codebase):
        """Verify worker reads assigned files."""
        result = await worker.execute(assignment, sample_codebase)
        
        assert "observations" in result
        assert result["files_analyzed"] > 0
    
    @pytest.mark.asyncio
    async def test_execute_extracts_rules(self, worker, assignment, sample_codebase):
        """Verify worker extracts rules from observations."""
        result = await worker.execute(assignment, sample_codebase)
        
        assert "rules" in result
        # Should have some rules (at least basic ones)
        assert isinstance(result["rules"], list)
    
    @pytest.mark.asyncio
    async def test_execute_builds_dependency_graph(self, worker, assignment, sample_codebase):
        """Verify worker builds dependency graph."""
        result = await worker.execute(assignment, sample_codebase)
        
        assert "dependency_graph" in result
        assert isinstance(result["dependency_graph"], dict)
    
    @pytest.mark.asyncio
    async def test_execute_handles_missing_files(self, worker, sample_codebase):
        """Verify worker handles missing files gracefully."""
        from domain.entities.worker_assignment import WorkerAssignment
        
        assignment = WorkerAssignment.create_analysis_assignment(
            files=["nonexistent.py"],
        )
        
        result = await worker.execute(assignment, sample_codebase)
        
        # Should not raise, but may have error
        assert result is not None
    
    @pytest.mark.asyncio
    async def test_execute_completes_assignment(self, worker, assignment, sample_codebase):
        """Verify assignment is marked as completed."""
        await worker.execute(assignment, sample_codebase)
        
        assert assignment.is_completed()
    
    @pytest.mark.asyncio
    async def test_basic_observations_without_ai(self, mock_prompt_loader, sample_codebase):
        """Verify basic observations work without AI client."""
        from application.agents.analysis_worker import AnalysisWorker
        from domain.entities.worker_assignment import WorkerAssignment
        
        # Create worker without AI client
        worker = AnalysisWorker(
            ai_client=None,
            prompt_loader=mock_prompt_loader,
        )
        
        assignment = WorkerAssignment.create_analysis_assignment(
            files=["src/handlers/user.py"],
        )
        
        result = await worker.execute(assignment, sample_codebase)
        
        assert result is not None
        assert "observations" in result
    
    def test_build_dependency_graph(self, worker):
        """Test dependency graph building."""
        file_contents = {
            "main.py": "from utils import helper\nimport json",
            "utils.py": "def helper(): pass",
        }
        
        graph = worker._build_dependency_graph(file_contents)
        
        assert "main.py" in graph
        assert "imports" in graph["main.py"]
        assert len(graph["main.py"]["imports"]) > 0
