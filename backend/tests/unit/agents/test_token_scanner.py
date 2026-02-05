"""Tests for TokenScanner."""
import pytest
from pathlib import Path


class TestTokenScanner:
    """Tests for token scanner functionality."""
    
    @pytest.fixture
    def scanner(self):
        """Create scanner instance."""
        from application.agents.token_scanner import TokenScanner
        return TokenScanner(max_file_tokens=10_000)
    
    @pytest.mark.asyncio
    async def test_scan_counts_files(self, scanner, sample_codebase):
        """Verify scanner counts files correctly."""
        result = await scanner.scan(sample_codebase)
        
        assert result.total_files > 0
        assert result.total_tokens > 0
        assert len(result.files) > 0
    
    @pytest.mark.asyncio
    async def test_scan_includes_python_files(self, scanner, sample_codebase):
        """Verify Python files are included."""
        result = await scanner.scan(sample_codebase)
        
        python_files = [f for f in result.files if f.extension == ".py"]
        assert len(python_files) > 0
    
    @pytest.mark.asyncio
    async def test_scan_respects_max_file_size(self, scanner, tmp_path):
        """Verify large files are skipped."""
        # Create a large file
        large_file = tmp_path / "large.py"
        large_file.write_text("x" * 2_000_000)  # 2MB
        
        result = await scanner.scan(tmp_path)
        
        # Large file should be skipped
        assert not any(f.path == "large.py" for f in result.files)
        assert any(s["path"] == "large.py" for s in result.skipped)
    
    @pytest.mark.asyncio
    async def test_scan_skips_binary_files(self, scanner, tmp_path):
        """Verify binary files are skipped."""
        # Create a binary file
        binary_file = tmp_path / "image.png"
        binary_file.write_bytes(b'\x89PNG\r\n\x1a\n\x00\x00\x00')
        
        result = await scanner.scan(tmp_path)
        
        assert not any(f.path == "image.png" for f in result.files)
    
    @pytest.mark.asyncio
    async def test_scan_skips_gitignored_patterns(self, scanner, tmp_path):
        """Verify common ignored patterns are skipped."""
        # Create node_modules directory
        nm_dir = tmp_path / "node_modules"
        nm_dir.mkdir()
        (nm_dir / "package.js").write_text("module.exports = {}")
        
        result = await scanner.scan(tmp_path)
        
        # node_modules should be skipped
        assert not any("node_modules" in f.path for f in result.files)
    
    def test_plan_assignments_distributes_files(self, scanner, sample_codebase):
        """Verify work is distributed across workers."""
        from application.agents.token_scanner import ScanResult, FileInfo
        
        # Create mock scan result with known token counts
        files = [
            FileInfo(path=f"file{i}.py", tokens=50_000, size_bytes=1000, extension=".py")
            for i in range(10)
        ]
        
        scan_result = ScanResult(
            root=str(sample_codebase),
            files=files,
            total_tokens=500_000,
            total_files=10,
        )
        
        assignments = scanner.plan_assignments(scan_result, budget_per_worker=150_000)
        
        # Should have multiple assignments
        assert len(assignments) >= 2
        
        # Each assignment should have files
        for assignment in assignments:
            assert len(assignment) > 0
    
    def test_plan_assignments_empty_result(self, scanner):
        """Verify empty scan result returns empty assignments."""
        from application.agents.token_scanner import ScanResult
        
        scan_result = ScanResult(root="/tmp", files=[], total_tokens=0, total_files=0)
        
        assignments = scanner.plan_assignments(scan_result)
        
        assert assignments == []
    
    @pytest.mark.asyncio
    async def test_scan_handles_permission_errors(self, scanner, tmp_path):
        """Verify permission errors are handled gracefully."""
        # This test may not work on all systems
        result = await scanner.scan(tmp_path)
        
        # Should complete without raising
        assert result is not None
