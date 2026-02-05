"""Architecture validator service for validating code against architecture rules."""
import logging
import re
from pathlib import Path
from typing import Any

from domain.entities.architecture_rule import ArchitectureRule
from domain.entities.validation_result import (
    ValidationReport,
    ValidationResult,
    Violation,
    ViolationSeverity,
)
from application.services.architecture_resolver import ArchitectureResolver

logger = logging.getLogger(__name__)


class ArchitectureValidator:
    """Validates code against architecture rules.
    
    This service provides synchronous validation of code against
    resolved architecture rules without requiring AI.
    """
    
    def __init__(
        self,
        resolver: ArchitectureResolver,
    ):
        """Initialize validator.
        
        Args:
            resolver: Architecture resolver for getting rules
        """
        self._resolver = resolver
    
    async def validate_file(
        self,
        repository_id: str,
        file_path: str,
        content: str,
    ) -> ValidationResult:
        """Validate a file against architecture rules.
        
        Args:
            repository_id: Repository ID
            file_path: Path to the file being validated
            content: File content
            
        Returns:
            ValidationResult with any violations
        """
        # Get resolved architecture
        architecture = await self._resolver.get_rules_for_repository(repository_id)
        
        violations = []
        
        # Check location rules
        location_violations = self._check_location(file_path, architecture.get_rules_by_type("location"))
        violations.extend(location_violations)
        
        # Check dependency rules
        dep_violations = self._check_dependencies(file_path, content, architecture.rules)
        violations.extend(dep_violations)
        
        # Check convention rules
        conv_violations = self._check_conventions(file_path, content, architecture.get_convention_rules())
        violations.extend(conv_violations)
        
        # Check boundary rules
        boundary_violations = self._check_boundaries(file_path, content, architecture.get_boundary_rules())
        violations.extend(boundary_violations)
        
        # Check layer rules (if applicable)
        layer_violations = self._check_layer_rules(file_path, content, architecture.get_layer_rules())
        violations.extend(layer_violations)
        
        # Create result
        if violations:
            return ValidationResult.create_invalid(
                file_path=file_path,
                violations=violations,
                rules_checked=len(architecture.rules),
            )
        else:
            return ValidationResult.create_valid(
                file_path=file_path,
                rules_checked=len(architecture.rules),
            )
    
    async def validate_change(
        self,
        repository_id: str,
        changed_files: list[dict[str, Any]],
    ) -> ValidationReport:
        """Validate a set of changes (e.g., PR validation).
        
        Args:
            repository_id: Repository ID
            changed_files: List of dicts with 'path' and 'content' keys
            
        Returns:
            ValidationReport with all results
        """
        results = []
        
        for file_change in changed_files:
            file_path = file_change.get("path", "")
            content = file_change.get("content", "")
            
            if file_path and content:
                result = await self.validate_file(repository_id, file_path, content)
                results.append(result)
        
        return ValidationReport.create(repository_id, results)
    
    async def check_file_location(
        self,
        repository_id: str,
        file_path: str,
    ) -> ValidationResult:
        """Check if a file is in the correct location.
        
        Args:
            repository_id: Repository ID
            file_path: Proposed file path
            
        Returns:
            ValidationResult
        """
        architecture = await self._resolver.get_rules_for_repository(repository_id)
        
        violations = self._check_location(file_path, architecture.get_rules_by_type("location"))
        
        if violations:
            return ValidationResult.create_invalid(
                file_path=file_path,
                violations=violations,
                rules_checked=len(architecture.get_rules_by_type("location")),
            )
        else:
            return ValidationResult.create_valid(
                file_path=file_path,
                rules_checked=len(architecture.get_rules_by_type("location")),
            )
    
    def _check_location(
        self,
        file_path: str,
        location_rules: list[ArchitectureRule],
    ) -> list[Violation]:
        """Check if file is in correct location.
        
        Args:
            file_path: File path
            location_rules: Location rules to check
            
        Returns:
            List of violations
        """
        violations = []
        
        # Infer file type from extension
        extension = Path(file_path).suffix.lower()
        file_type = self._get_file_type(extension)
        
        for rule in location_rules:
            rule_data = rule.rule_data
            expected_path = rule_data.get("path", "")
            expected_types = rule_data.get("file_types", [])
            purpose = rule_data.get("purpose", "")
            
            # Skip if rule doesn't apply to this file type
            if expected_types and file_type not in expected_types:
                continue
            
            # Check if file should be in this location based on purpose
            if purpose:
                # Use heuristics to match file to purpose
                file_name = Path(file_path).stem.lower()
                
                purpose_keywords = {
                    "test": ["test", "spec", "_test", "test_"],
                    "config": ["config", "settings", "env"],
                    "route": ["route", "handler", "endpoint", "api"],
                    "service": ["service", "manager", "processor"],
                    "entity": ["entity", "model", "domain"],
                    "repository": ["repository", "repo", "store", "persistence"],
                }
                
                for keyword_type, keywords in purpose_keywords.items():
                    if any(kw in file_name for kw in keywords):
                        # Check if file is in expected location for this type
                        if keyword_type in purpose.lower():
                            if expected_path and not file_path.startswith(expected_path.rstrip("/")):
                                violation = Violation.create(
                                    rule_id=rule.rule_id,
                                    rule_type="location",
                                    severity=ViolationSeverity.WARNING,
                                    message=f"File appears to be a {keyword_type} file but is not in expected location '{expected_path}'",
                                    file_path=file_path,
                                    suggestion=f"Consider moving to {expected_path}",
                                )
                                violations.append(violation)
        
        return violations
    
    def _check_dependencies(
        self,
        file_path: str,
        content: str,
        rules: list[ArchitectureRule],
    ) -> list[Violation]:
        """Check dependency/import rules.
        
        Args:
            file_path: File path
            content: File content
            rules: All rules
            
        Returns:
            List of violations
        """
        violations = []
        
        # Extract imports
        imports = self._extract_imports(content, file_path)
        
        # Get dependency rules
        dep_rules = [r for r in rules if r.rule_type in ["dependency", "layer"]]
        
        for rule in dep_rules:
            rule_data = rule.rule_data
            
            # Check forbidden imports
            forbidden = rule_data.get("forbidden_imports", [])
            for imp in imports:
                for forbidden_pattern in forbidden:
                    if self._matches_pattern(imp, forbidden_pattern):
                        violation = Violation.create(
                            rule_id=rule.rule_id,
                            rule_type="dependency",
                            severity=ViolationSeverity.ERROR,
                            message=f"Import '{imp}' violates dependency rule: matches forbidden pattern '{forbidden_pattern}'",
                            file_path=file_path,
                            suggestion=f"Remove or replace import '{imp}'",
                        )
                        violations.append(violation)
        
        return violations
    
    def _check_conventions(
        self,
        file_path: str,
        content: str,
        convention_rules: list[ArchitectureRule],
    ) -> list[Violation]:
        """Check naming and structural conventions.
        
        Args:
            file_path: File path
            content: File content
            convention_rules: Convention rules
            
        Returns:
            List of violations
        """
        violations = []
        
        for rule in convention_rules:
            rule_data = rule.rule_data
            pattern_type = rule_data.get("pattern_type", "")
            pattern = rule_data.get("pattern", "")
            
            if pattern_type == "naming" and pattern:
                # Check file name against pattern
                file_name = Path(file_path).name
                if not self._matches_pattern(file_name, pattern):
                    # Only warn if this rule seems to apply
                    examples = rule_data.get("examples", [])
                    if examples:
                        # Check if file is similar to examples
                        for example in examples:
                            if self._similar_path(file_path, example):
                                violation = Violation.create(
                                    rule_id=rule.rule_id,
                                    rule_type="convention",
                                    severity=ViolationSeverity.INFO,
                                    message=f"File name doesn't follow observed convention: {rule.name}",
                                    file_path=file_path,
                                    suggestion=f"Consider following pattern: {pattern}",
                                )
                                violations.append(violation)
                                break
        
        return violations
    
    def _check_boundaries(
        self,
        file_path: str,
        content: str,
        boundary_rules: list[ArchitectureRule],
    ) -> list[Violation]:
        """Check boundary rules.
        
        Args:
            file_path: File path
            content: File content
            boundary_rules: Boundary rules
            
        Returns:
            List of violations
        """
        violations = []
        
        # Extract imports
        imports = self._extract_imports(content, file_path)
        
        for rule in boundary_rules:
            rule_data = rule.rule_data
            component_a = rule_data.get("component_a", "")
            component_b = rule_data.get("component_b", "")
            relationship = rule_data.get("relationship", "")
            
            # Check if file is in component_a
            if component_a and component_a in file_path:
                # Check relationship
                if "does not import" in relationship.lower():
                    for imp in imports:
                        if component_b and component_b in imp:
                            violation = Violation.create(
                                rule_id=rule.rule_id,
                                rule_type="boundary",
                                severity=ViolationSeverity.ERROR,
                                message=f"Boundary violation: {relationship}",
                                file_path=file_path,
                                suggestion=f"Remove dependency on '{component_b}' or use an intermediary",
                            )
                            violations.append(violation)
        
        return violations
    
    def _check_layer_rules(
        self,
        file_path: str,
        content: str,
        layer_rules: list[ArchitectureRule],
    ) -> list[Violation]:
        """Check layer dependency rules.
        
        Args:
            file_path: File path
            content: File content
            layer_rules: Layer rules
            
        Returns:
            List of violations
        """
        violations = []
        
        # Find which layer this file belongs to
        file_layer = None
        for rule in layer_rules:
            rule_data = rule.rule_data
            location = rule_data.get("location", "")
            if location and file_path.startswith(location.rstrip("/")):
                file_layer = rule
                break
        
        if not file_layer:
            return violations
        
        # Get allowed dependencies for this layer
        allowed_deps = file_layer.rule_data.get("depends_on", [])
        
        # Extract imports
        imports = self._extract_imports(content, file_path)
        
        # Check each import against layer rules
        for imp in imports:
            # Determine which layer the import is from
            import_layer = None
            for rule in layer_rules:
                rule_data = rule.rule_data
                location = rule_data.get("location", "")
                if location and imp.startswith(location.rstrip("/")):
                    import_layer = rule.name
                    break
            
            # Check if import is allowed
            if import_layer and import_layer not in allowed_deps:
                if import_layer != file_layer.name:  # Same layer is always OK
                    violation = Violation.create(
                        rule_id=file_layer.rule_id,
                        rule_type="layer",
                        severity=ViolationSeverity.ERROR,
                        message=f"Layer violation: '{file_layer.name}' should not import from '{import_layer}'",
                        file_path=file_path,
                        suggestion=f"Allowed dependencies: {', '.join(allowed_deps)}",
                    )
                    violations.append(violation)
        
        return violations
    
    def _extract_imports(self, content: str, file_path: str) -> list[str]:
        """Extract import statements from content.
        
        Args:
            content: File content
            file_path: File path (for determining file type)
            
        Returns:
            List of import paths
        """
        imports = []
        
        if file_path.endswith(".py"):
            # Python imports
            patterns = [
                r'^import\s+([\w.]+)',
                r'^from\s+([\w.]+)\s+import',
            ]
            for pattern in patterns:
                matches = re.findall(pattern, content, re.MULTILINE)
                imports.extend(matches)
        
        elif file_path.endswith((".js", ".ts", ".jsx", ".tsx")):
            # JavaScript/TypeScript imports
            patterns = [
                r'import\s+.*?\s+from\s+[\'"]([^"\']+)[\'"]',
                r'require\s*\(\s*[\'"]([^"\']+)[\'"]\s*\)',
            ]
            for pattern in patterns:
                matches = re.findall(pattern, content)
                imports.extend(matches)
        
        return imports
    
    def _matches_pattern(self, value: str, pattern: str) -> bool:
        """Check if value matches a pattern.
        
        Args:
            value: Value to check
            pattern: Pattern (supports * wildcards)
            
        Returns:
            True if matches
        """
        import fnmatch
        return fnmatch.fnmatch(value, pattern) or pattern in value
    
    def _similar_path(self, path1: str, path2: str) -> bool:
        """Check if two paths are similar.
        
        Args:
            path1: First path
            path2: Second path
            
        Returns:
            True if similar
        """
        # Paths are similar if they share parent directory
        parts1 = path1.split("/")
        parts2 = path2.split("/")
        
        if len(parts1) < 2 or len(parts2) < 2:
            return False
        
        return parts1[:-1] == parts2[:-1]
    
    def _get_file_type(self, extension: str) -> str:
        """Get file type from extension.
        
        Args:
            extension: File extension (e.g., '.py')
            
        Returns:
            File type string
        """
        type_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".jsx": "javascript",
            ".go": "go",
            ".rs": "rust",
            ".java": "java",
            ".rb": "ruby",
            ".php": "php",
            ".css": "css",
            ".scss": "scss",
            ".html": "html",
            ".json": "json",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".md": "markdown",
            ".sql": "sql",
        }
        return type_map.get(extension, "unknown")
