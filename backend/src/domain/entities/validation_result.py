"""Validation result domain entities."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Self
import uuid


class ViolationSeverity(str, Enum):
    """Severity levels for architecture violations."""
    ERROR = "error"      # Must be fixed
    WARNING = "warning"  # Should be fixed
    INFO = "info"        # Informational only


@dataclass
class Violation:
    """Represents a single architecture violation."""
    
    id: str
    rule_id: str
    rule_type: str
    severity: ViolationSeverity
    message: str
    file_path: str
    line_number: int | None = None
    column_number: int | None = None
    suggestion: str | None = None
    related_rule_data: dict[str, Any] | None = None
    
    @classmethod
    def create(
        cls,
        rule_id: str,
        rule_type: str,
        severity: ViolationSeverity,
        message: str,
        file_path: str,
        line_number: int | None = None,
        suggestion: str | None = None,
        related_rule_data: dict[str, Any] | None = None,
    ) -> Self:
        """Factory method for creating a violation."""
        return cls(
            id=str(uuid.uuid4()),
            rule_id=rule_id,
            rule_type=rule_type,
            severity=severity,
            message=message,
            file_path=file_path,
            line_number=line_number,
            suggestion=suggestion,
            related_rule_data=related_rule_data,
        )
    
    def to_dict(self) -> dict[str, Any]:
        """Convert violation to dictionary for serialization."""
        result = {
            "id": self.id,
            "rule_id": self.rule_id,
            "rule_type": self.rule_type,
            "severity": self.severity.value,
            "message": self.message,
            "file_path": self.file_path,
        }
        
        if self.line_number is not None:
            result["line_number"] = self.line_number
        if self.column_number is not None:
            result["column_number"] = self.column_number
        if self.suggestion:
            result["suggestion"] = self.suggestion
        if self.related_rule_data:
            result["related_rule_data"] = self.related_rule_data
            
        return result


@dataclass
class ValidationResult:
    """Result of validating a single file against architecture rules."""
    
    file_path: str
    is_valid: bool
    violations: list[Violation] = field(default_factory=list)
    rules_checked: int = 0
    timestamp: datetime | None = None
    
    @classmethod
    def create_valid(cls, file_path: str, rules_checked: int = 0) -> Self:
        """Factory method for creating a valid result."""
        return cls(
            file_path=file_path,
            is_valid=True,
            violations=[],
            rules_checked=rules_checked,
            timestamp=datetime.now(timezone.utc),
        )
    
    @classmethod
    def create_invalid(
        cls,
        file_path: str,
        violations: list[Violation],
        rules_checked: int = 0,
    ) -> Self:
        """Factory method for creating an invalid result."""
        return cls(
            file_path=file_path,
            is_valid=False,
            violations=violations,
            rules_checked=rules_checked,
            timestamp=datetime.now(timezone.utc),
        )
    
    def add_violation(self, violation: Violation) -> None:
        """Add a violation to the result."""
        self.violations.append(violation)
        self.is_valid = False
    
    def error_count(self) -> int:
        """Count violations with ERROR severity."""
        return sum(1 for v in self.violations if v.severity == ViolationSeverity.ERROR)
    
    def warning_count(self) -> int:
        """Count violations with WARNING severity."""
        return sum(1 for v in self.violations if v.severity == ViolationSeverity.WARNING)
    
    def info_count(self) -> int:
        """Count violations with INFO severity."""
        return sum(1 for v in self.violations if v.severity == ViolationSeverity.INFO)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary for serialization."""
        return {
            "file_path": self.file_path,
            "is_valid": self.is_valid,
            "violations": [v.to_dict() for v in self.violations],
            "rules_checked": self.rules_checked,
            "error_count": self.error_count(),
            "warning_count": self.warning_count(),
            "info_count": self.info_count(),
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }


@dataclass
class ValidationReport:
    """Report for validating multiple files (e.g., PR validation)."""
    
    id: str
    repository_id: str
    total_files: int
    valid_files: int
    invalid_files: int
    results: list[ValidationResult] = field(default_factory=list)
    total_errors: int = 0
    total_warnings: int = 0
    total_info: int = 0
    created_at: datetime | None = None
    
    @classmethod
    def create(cls, repository_id: str, results: list[ValidationResult]) -> Self:
        """Factory method for creating a validation report."""
        valid_count = sum(1 for r in results if r.is_valid)
        invalid_count = len(results) - valid_count
        
        total_errors = sum(r.error_count() for r in results)
        total_warnings = sum(r.warning_count() for r in results)
        total_info = sum(r.info_count() for r in results)
        
        return cls(
            id=str(uuid.uuid4()),
            repository_id=repository_id,
            total_files=len(results),
            valid_files=valid_count,
            invalid_files=invalid_count,
            results=results,
            total_errors=total_errors,
            total_warnings=total_warnings,
            total_info=total_info,
            created_at=datetime.now(timezone.utc),
        )
    
    def is_passing(self) -> bool:
        """Check if validation passed (no errors)."""
        return self.total_errors == 0
    
    def get_all_violations(self) -> list[Violation]:
        """Get all violations from all results."""
        violations = []
        for result in self.results:
            violations.extend(result.violations)
        return violations
    
    def to_dict(self) -> dict[str, Any]:
        """Convert report to dictionary for serialization."""
        return {
            "id": self.id,
            "repository_id": self.repository_id,
            "is_passing": self.is_passing(),
            "total_files": self.total_files,
            "valid_files": self.valid_files,
            "invalid_files": self.invalid_files,
            "total_errors": self.total_errors,
            "total_warnings": self.total_warnings,
            "total_info": self.total_info,
            "results": [r.to_dict() for r in self.results],
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
