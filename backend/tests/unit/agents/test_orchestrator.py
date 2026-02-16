"""Tests for ArchitectureOrchestrator."""
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch


class TestArchitectureOrchestrator:
    """Tests for orchestrator functionality."""
    
    @pytest.fixture
    def orchestrator(self, mock_ai_client, mock_prompt_loader):
        """Create orchestrator instance."""
        from application.agents.orchestrator import ArchitectureOrchestrator
        return ArchitectureOrchestrator(
            ai_client=mock_ai_client,
            prompt_loader=mock_prompt_loader,
            worker_budget=150_000,
        )
    
    @pytest.mark.asyncio
    async def test_analyze_repository_scans_files(self, orchestrator, sample_codebase):
        """Verify orchestrator scans repository files."""
        result = await orchestrator.analyze_repository(
            repo_path=sample_codebase,
            repository_id="test-repo-123",
        )
        
        assert result is not None
        assert "total_files_analyzed" in result
        assert result["total_files_analyzed"] > 0
    
    @pytest.mark.asyncio
    async def test_analyze_repository_extracts_rules(self, orchestrator, sample_codebase):
        """Verify orchestrator extracts rules."""
        result = await orchestrator.analyze_repository(
            repo_path=sample_codebase,
            repository_id="test-repo-123",
        )
        
        assert "rules" in result
        assert isinstance(result["rules"], list)
    
    @pytest.mark.asyncio
    async def test_analyze_repository_returns_observations(self, orchestrator, sample_codebase):
        """Verify orchestrator returns observations."""
        result = await orchestrator.analyze_repository(
            repo_path=sample_codebase,
            repository_id="test-repo-123",
        )
        
        assert "observations" in result
    
    def test_plan_analysis_creates_assignments(self, orchestrator, sample_codebase):
        """Verify orchestrator creates worker assignments."""
        from application.agents.token_scanner import ScanResult, FileInfo
        
        scan_result = ScanResult(
            root=str(sample_codebase),
            files=[
                FileInfo(path="file1.py", tokens=50_000, size_bytes=1000, extension=".py"),
                FileInfo(path="file2.py", tokens=50_000, size_bytes=1000, extension=".py"),
            ],
            total_tokens=100_000,
            total_files=2,
        )
        
        plan = orchestrator._plan_analysis(scan_result, "test-repo")
        
        assert len(plan.assignments) > 0
        assert plan.total_files == 2
    
    def test_synthesize_results_deduplicates_rules(self, orchestrator):
        """Verify synthesizer deduplicates rules."""
        worker_results = [
            {
                "rules": [
                    {"rule_type": "purpose", "rule_id": "rule-1", "name": "Rule 1", "rule_data": {}},
                    {"rule_type": "purpose", "rule_id": "rule-2", "name": "Rule 2", "rule_data": {}},
                ],
                "observations": {},
                "files_analyzed": 2,
            },
            {
                "rules": [
                    {"rule_type": "purpose", "rule_id": "rule-1", "name": "Rule 1", "rule_data": {}},  # Duplicate
                    {"rule_type": "purpose", "rule_id": "rule-3", "name": "Rule 3", "rule_data": {}},
                ],
                "observations": {},
                "files_analyzed": 2,
            },
        ]
        
        synthesized = orchestrator._synthesize_results(worker_results, "test-repo", "analysis-1")
        
        # Should have 3 unique rules, not 4
        assert synthesized["total_rules"] == 3
    
    @pytest.mark.asyncio
    async def test_validate_files(self, orchestrator, sample_codebase, sample_architecture_rules):
        """Verify orchestrator can validate files."""
        report = await orchestrator.validate_files(
            repo_path=sample_codebase,
            repository_id="test-repo-123",
            file_paths=["src/handlers/user.py"],
            rules=sample_architecture_rules,
        )
        
        assert report is not None
        assert report.total_files == 1
    
    @pytest.mark.asyncio
    async def test_detect_changes(self, orchestrator, sample_codebase):
        """Verify orchestrator can detect changes."""
        result = await orchestrator.detect_changes(
            repo_path=sample_codebase,
            repository_id="test-repo-123",
        )
        
        assert result is not None
        assert "recommendation" in result
