"""Tests for ValidationWorker."""
import pytest
from pathlib import Path


class TestValidationWorker:
    """Tests for validation worker functionality."""
    
    @pytest.fixture
    def worker(self, mock_ai_client, mock_prompt_loader):
        """Create validation worker instance."""
        from application.agents.validation_worker import ValidationWorker
        return ValidationWorker(
            ai_client=mock_ai_client,
            prompt_loader=mock_prompt_loader,
        )
    
    @pytest.fixture
    def assignment_with_rules(self, sample_architecture_rules):
        """Create assignment with rules in context."""
        from domain.entities.worker_assignment import WorkerAssignment
        
        return WorkerAssignment.create_validation_assignment(
            files=["src/handlers/user.py"],
            context={
                "rules": [r.to_dict() for r in sample_architecture_rules],
            },
        )
    
    @pytest.mark.asyncio
    async def test_execute_validates_files(self, worker, assignment_with_rules, sample_codebase):
        """Verify worker validates assigned files."""
        result = await worker.execute(assignment_with_rules, sample_codebase)
        
        assert "results" in result
        assert len(result["results"]) > 0
    
    @pytest.mark.asyncio
    async def test_execute_reports_validation_status(self, worker, assignment_with_rules, sample_codebase):
        """Verify worker reports validation status."""
        result = await worker.execute(assignment_with_rules, sample_codebase)
        
        assert "total_files" in result
        assert "total_violations" in result
        assert "is_valid" in result
    
    @pytest.mark.asyncio
    async def test_execute_handles_empty_rules(self, worker, sample_codebase):
        """Verify worker handles empty rules."""
        from domain.entities.worker_assignment import WorkerAssignment
        
        assignment = WorkerAssignment.create_validation_assignment(
            files=["src/handlers/user.py"],
            context={"rules": []},
        )
        
        result = await worker.execute(assignment, sample_codebase)
        
        assert result is not None
        assert result.get("is_valid", True)  # No rules = valid
    
    @pytest.mark.asyncio
    async def test_detects_dependency_violations(self, worker, sample_codebase):
        """Verify worker detects dependency violations."""
        from domain.entities.worker_assignment import WorkerAssignment
        
        # Create a rule that forbids certain imports
        assignment = WorkerAssignment.create_validation_assignment(
            files=["src/handlers/user.py"],
            context={
                "rules": [{
                    "rule_type": "dependency",
                    "rule_id": "dep-forbidden",
                    "name": "Forbidden imports",
                    "rule_data": {
                        "forbidden_imports": ["src.services.*"],
                    },
                }],
            },
        )
        
        result = await worker.execute(assignment, sample_codebase)
        
        # The handler imports from services, so there should be violations
        assert result["total_violations"] > 0 or result["is_valid"] is False
    
    def test_matches_pattern(self, worker):
        """Test pattern matching utility."""
        assert worker._matches_pattern("user_service.py", "*_service.py")
        assert worker._matches_pattern("UserService", "Service")
        assert not worker._matches_pattern("user.py", "*_service.py")
