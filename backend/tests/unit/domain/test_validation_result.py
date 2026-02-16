"""Tests for ValidationResult domain entities."""
import pytest


class TestViolation:
    """Tests for Violation entity."""
    
    def test_create_violation(self):
        """Test creating a violation."""
        from domain.entities.validation_result import Violation, ViolationSeverity
        
        violation = Violation.create(
            rule_id="dep-forbidden",
            rule_type="dependency",
            severity=ViolationSeverity.ERROR,
            message="Forbidden import detected",
            file_path="src/handlers/user.py",
            line_number=5,
            suggestion="Remove this import",
        )
        
        assert violation.rule_id == "dep-forbidden"
        assert violation.severity == ViolationSeverity.ERROR
        assert violation.line_number == 5
    
    def test_violation_to_dict(self):
        """Test converting violation to dictionary."""
        from domain.entities.validation_result import Violation, ViolationSeverity
        
        violation = Violation.create(
            rule_id="test-rule",
            rule_type="test",
            severity=ViolationSeverity.WARNING,
            message="Test message",
            file_path="test.py",
        )
        
        d = violation.to_dict()
        
        assert d["rule_id"] == "test-rule"
        assert d["severity"] == "warning"
        assert d["file_path"] == "test.py"


class TestValidationResult:
    """Tests for ValidationResult entity."""
    
    def test_create_valid_result(self):
        """Test creating a valid result."""
        from domain.entities.validation_result import ValidationResult
        
        result = ValidationResult.create_valid(
            file_path="test.py",
            rules_checked=10,
        )
        
        assert result.is_valid is True
        assert result.rules_checked == 10
        assert len(result.violations) == 0
    
    def test_create_invalid_result(self):
        """Test creating an invalid result."""
        from domain.entities.validation_result import (
            ValidationResult,
            Violation,
            ViolationSeverity,
        )
        
        violations = [
            Violation.create(
                rule_id="rule-1",
                rule_type="test",
                severity=ViolationSeverity.ERROR,
                message="Error",
                file_path="test.py",
            )
        ]
        
        result = ValidationResult.create_invalid(
            file_path="test.py",
            violations=violations,
            rules_checked=5,
        )
        
        assert result.is_valid is False
        assert len(result.violations) == 1
    
    def test_add_violation(self):
        """Test adding a violation to result."""
        from domain.entities.validation_result import (
            ValidationResult,
            Violation,
            ViolationSeverity,
        )
        
        result = ValidationResult.create_valid(file_path="test.py")
        
        violation = Violation.create(
            rule_id="rule-1",
            rule_type="test",
            severity=ViolationSeverity.WARNING,
            message="Warning",
            file_path="test.py",
        )
        
        result.add_violation(violation)
        
        assert result.is_valid is False
        assert len(result.violations) == 1
    
    def test_count_by_severity(self):
        """Test counting violations by severity."""
        from domain.entities.validation_result import (
            ValidationResult,
            Violation,
            ViolationSeverity,
        )
        
        violations = [
            Violation.create("r1", "t", ViolationSeverity.ERROR, "m", "f.py"),
            Violation.create("r2", "t", ViolationSeverity.ERROR, "m", "f.py"),
            Violation.create("r3", "t", ViolationSeverity.WARNING, "m", "f.py"),
            Violation.create("r4", "t", ViolationSeverity.INFO, "m", "f.py"),
        ]
        
        result = ValidationResult.create_invalid("test.py", violations)
        
        assert result.error_count() == 2
        assert result.warning_count() == 1
        assert result.info_count() == 1


class TestValidationReport:
    """Tests for ValidationReport entity."""
    
    def test_create_report(self):
        """Test creating a validation report."""
        from domain.entities.validation_result import (
            ValidationReport,
            ValidationResult,
        )
        
        results = [
            ValidationResult.create_valid("file1.py"),
            ValidationResult.create_valid("file2.py"),
        ]
        
        report = ValidationReport.create("repo-123", results)
        
        assert report.total_files == 2
        assert report.valid_files == 2
        assert report.invalid_files == 0
    
    def test_is_passing(self):
        """Test is_passing check."""
        from domain.entities.validation_result import (
            ValidationReport,
            ValidationResult,
            Violation,
            ViolationSeverity,
        )
        
        # Report with no errors should pass
        results = [ValidationResult.create_valid("file.py")]
        report = ValidationReport.create("repo", results)
        assert report.is_passing() is True
        
        # Report with errors should not pass
        error_result = ValidationResult.create_invalid(
            "bad.py",
            [Violation.create("r", "t", ViolationSeverity.ERROR, "m", "bad.py")],
        )
        report2 = ValidationReport.create("repo", [error_result])
        assert report2.is_passing() is False
    
    def test_get_all_violations(self):
        """Test getting all violations from report."""
        from domain.entities.validation_result import (
            ValidationReport,
            ValidationResult,
            Violation,
            ViolationSeverity,
        )
        
        results = [
            ValidationResult.create_invalid(
                "file1.py",
                [Violation.create("r1", "t", ViolationSeverity.ERROR, "m1", "file1.py")],
            ),
            ValidationResult.create_invalid(
                "file2.py",
                [Violation.create("r2", "t", ViolationSeverity.WARNING, "m2", "file2.py")],
            ),
        ]
        
        report = ValidationReport.create("repo", results)
        violations = report.get_all_violations()
        
        assert len(violations) == 2
