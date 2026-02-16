"""Validation worker for checking code against architecture rules."""
import logging
from pathlib import Path
from typing import Any

from anthropic import AsyncAnthropic

from application.agents.base_worker import BaseWorker
from domain.entities.architecture_rule import ArchitectureRule
from domain.entities.validation_result import (
    ValidationResult,
    Violation,
    ViolationSeverity,
)
from domain.entities.worker_assignment import WorkerAssignment
from infrastructure.prompts.prompt_loader import PromptLoader

logger = logging.getLogger(__name__)


class ValidationWorker(BaseWorker):
    """Worker that validates code against architecture rules.
    
    This worker:
    - Checks if file locations follow conventions
    - Validates imports follow dependency rules
    - Checks naming conventions
    - Validates boundary rules
    """
    
    def __init__(
        self,
        ai_client: AsyncAnthropic | None,
        prompt_loader: PromptLoader,
        model: str = "claude-sonnet-4-20250514",
    ):
        """Initialize validation worker."""
        super().__init__(ai_client, prompt_loader, model)
    
    async def execute(
        self,
        assignment: WorkerAssignment,
        repo_path: Path,
    ) -> dict[str, Any]:
        """Execute validation assignment.
        
        Args:
            assignment: Work assignment with files to validate
            repo_path: Path to repository
            
        Returns:
            Dictionary with validation results
        """
        assignment.start()
        
        try:
            # Get architecture rules from context
            rules_data = assignment.context.get("rules", [])
            rules = self._parse_rules(rules_data)
            
            results: list[ValidationResult] = []
            
            for file_path in assignment.files:
                content = await self.read_file(repo_path / file_path)
                if content:
                    result = await self._validate_file(
                        file_path,
                        content,
                        rules,
                    )
                    results.append(result)
            
            # Summarize results
            total_violations = sum(len(r.violations) for r in results)
            total_errors = sum(r.error_count() for r in results)
            total_warnings = sum(r.warning_count() for r in results)
            
            result_dict = {
                "results": [r.to_dict() for r in results],
                "total_files": len(results),
                "total_violations": total_violations,
                "total_errors": total_errors,
                "total_warnings": total_warnings,
                "is_valid": total_errors == 0,
            }
            
            assignment.complete(result_dict)
            return result_dict
            
        except Exception as e:
            logger.error(f"Validation worker failed: {e}")
            assignment.fail(str(e))
            return {
                "results": [],
                "error": str(e),
            }
    
    def _parse_rules(self, rules_data: list[dict[str, Any]]) -> list[ArchitectureRule]:
        """Parse rules from context data.
        
        Args:
            rules_data: List of rule dictionaries
            
        Returns:
            List of ArchitectureRule objects
        """
        rules = []
        for rule_dict in rules_data:
            try:
                rule = ArchitectureRule(
                    id=rule_dict.get("id", ""),
                    rule_type=rule_dict.get("rule_type", ""),
                    rule_id=rule_dict.get("rule_id", ""),
                    name=rule_dict.get("name", ""),
                    description=rule_dict.get("description"),
                    rule_data=rule_dict.get("rule_data", {}),
                    confidence=rule_dict.get("confidence", 1.0),
                    source_files=rule_dict.get("source_files"),
                )
                rules.append(rule)
            except Exception as e:
                logger.warning(f"Failed to parse rule: {e}")
        return rules
    
    async def _validate_file(
        self,
        file_path: str,
        content: str,
        rules: list[ArchitectureRule],
    ) -> ValidationResult:
        """Validate a single file against rules.
        
        Args:
            file_path: Path to file
            content: File content
            rules: Rules to validate against
            
        Returns:
            ValidationResult
        """
        # First, do basic programmatic validation
        violations = []
        
        # Apply dependency rules
        dep_violations = self._check_dependency_rules(file_path, content, rules)
        violations.extend(dep_violations)
        
        # Apply convention rules
        conv_violations = self._check_convention_rules(file_path, content, rules)
        violations.extend(conv_violations)
        
        # Apply boundary rules
        boundary_violations = self._check_boundary_rules(file_path, content, rules)
        violations.extend(boundary_violations)
        
        # If AI is available, do more sophisticated validation
        if self._ai_client and rules:
            ai_violations = await self._ai_validate(file_path, content, rules)
            violations.extend(ai_violations)
        
        # Create result
        if violations:
            return ValidationResult.create_invalid(
                file_path=file_path,
                violations=violations,
                rules_checked=len(rules),
            )
        else:
            return ValidationResult.create_valid(
                file_path=file_path,
                rules_checked=len(rules),
            )
    
    def _check_dependency_rules(
        self,
        file_path: str,
        content: str,
        rules: list[ArchitectureRule],
    ) -> list[Violation]:
        """Check dependency rules.
        
        Args:
            file_path: File path
            content: File content
            rules: Rules to check
            
        Returns:
            List of violations
        """
        import re
        
        violations = []
        
        # Extract imports from file
        imports = []
        
        # Python imports
        python_patterns = [
            r'^import\s+([\w.]+)',
            r'^from\s+([\w.]+)\s+import',
        ]
        for pattern in python_patterns:
            matches = re.findall(pattern, content, re.MULTILINE)
            imports.extend(matches)
        
        # JS/TS imports
        js_patterns = [
            r'import\s+.*?\s+from\s+[\'"]([^"\']+)[\'"]',
            r'require\s*\(\s*[\'"]([^"\']+)[\'"]\s*\)',
        ]
        for pattern in js_patterns:
            matches = re.findall(pattern, content)
            imports.extend(matches)
        
        # Check against dependency rules
        dep_rules = [r for r in rules if r.rule_type == "dependency"]
        
        for rule in dep_rules:
            rule_data = rule.rule_data
            
            # Check if rule applies to this file
            source_pattern = rule_data.get("source_pattern", "")
            if source_pattern and not self._matches_pattern(file_path, source_pattern):
                continue
            
            # Check forbidden imports
            forbidden = rule_data.get("forbidden_imports", [])
            for imp in imports:
                for forbidden_pattern in forbidden:
                    if self._matches_pattern(imp, forbidden_pattern):
                        violation = Violation.create(
                            rule_id=rule.rule_id,
                            rule_type="dependency",
                            severity=ViolationSeverity.ERROR,
                            message=f"Import '{imp}' violates dependency rule: forbidden import pattern '{forbidden_pattern}'",
                            file_path=file_path,
                            suggestion=f"Remove or replace import '{imp}' with an allowed dependency",
                        )
                        violations.append(violation)
        
        return violations
    
    def _check_convention_rules(
        self,
        file_path: str,
        content: str,
        rules: list[ArchitectureRule],
    ) -> list[Violation]:
        """Check convention rules.
        
        Args:
            file_path: File path
            content: File content
            rules: Rules to check
            
        Returns:
            List of violations
        """
        violations = []
        
        conv_rules = [r for r in rules if r.rule_type == "convention"]
        
        for rule in conv_rules:
            rule_data = rule.rule_data
            pattern_type = rule_data.get("pattern_type", "")
            
            if pattern_type == "naming":
                # Check file naming convention
                expected_pattern = rule_data.get("pattern", "")
                if expected_pattern and not self._matches_pattern(file_path, expected_pattern):
                    violation = Violation.create(
                        rule_id=rule.rule_id,
                        rule_type="convention",
                        severity=ViolationSeverity.WARNING,
                        message=f"File name doesn't match naming convention: expected pattern '{expected_pattern}'",
                        file_path=file_path,
                        suggestion=f"Rename file to match convention: {expected_pattern}",
                    )
                    violations.append(violation)
        
        return violations
    
    def _check_boundary_rules(
        self,
        file_path: str,
        content: str,
        rules: list[ArchitectureRule],
    ) -> list[Violation]:
        """Check boundary rules.
        
        Args:
            file_path: File path
            content: File content
            rules: Rules to check
            
        Returns:
            List of violations
        """
        import re
        
        violations = []
        
        boundary_rules = [r for r in rules if r.rule_type == "boundary"]
        
        # Extract imports
        imports = []
        for pattern in [r'^import\s+([\w.]+)', r'^from\s+([\w.]+)\s+import']:
            imports.extend(re.findall(pattern, content, re.MULTILINE))
        for pattern in [r'import\s+.*?\s+from\s+[\'"]([^"\']+)[\'"]']:
            imports.extend(re.findall(pattern, content))
        
        for rule in boundary_rules:
            rule_data = rule.rule_data
            component_a = rule_data.get("component_a", "")
            component_b = rule_data.get("component_b", "")
            relationship = rule_data.get("relationship", "")
            
            # Check if this file is in component_a
            if component_a and component_a in file_path:
                # Check if it imports from component_b when it shouldn't
                if "does not import" in relationship.lower():
                    for imp in imports:
                        if component_b and component_b in imp:
                            violation = Violation.create(
                                rule_id=rule.rule_id,
                                rule_type="boundary",
                                severity=ViolationSeverity.ERROR,
                                message=f"Boundary violation: '{component_a}' should not import from '{component_b}'",
                                file_path=file_path,
                                suggestion=f"Remove dependency on '{component_b}' or use an intermediary",
                                related_rule_data=rule_data,
                            )
                            violations.append(violation)
        
        return violations
    
    async def _ai_validate(
        self,
        file_path: str,
        content: str,
        rules: list[ArchitectureRule],
    ) -> list[Violation]:
        """Use AI for more sophisticated validation.
        
        Args:
            file_path: File path
            content: File content
            rules: Rules to validate against
            
        Returns:
            List of additional violations found by AI
        """
        # Get validation prompt
        prompt_template = self._prompt_loader.get_prompt_by_key("worker_validate_code")
        
        # Format rules for prompt
        import json
        rules_for_prompt = [
            {
                "rule_id": r.rule_id,
                "rule_type": r.rule_type,
                "name": r.name,
                "description": r.description,
                "rule_data": r.rule_data,
            }
            for r in rules[:20]  # Limit rules to fit in context
        ]
        rules_str = json.dumps(rules_for_prompt, indent=2)
        
        # Truncate content if needed
        truncated_content = content[:10_000]
        if len(content) > 10_000:
            truncated_content += "\n... (truncated)"
        
        if prompt_template and hasattr(prompt_template, 'render'):
            prompt = prompt_template.render({
                "file_path": file_path,
                "code_content": truncated_content,
                "architecture_rules": rules_str,
            })
        else:
            prompt = f"""Validate this code against the architecture rules.

## Code to Validate
File: {file_path}
```
{truncated_content}
```

## Architecture Rules
{rules_str}

Return a JSON object with violations found (empty array if code is valid):
{{"violations": [
  {{"rule_id": "...", "rule_type": "...", "severity": "error|warning|info", "message": "...", "line_number": null, "suggestion": "..."}}
]}}"""
        
        response = await self._call_ai(prompt, max_tokens=2000)
        
        if not response:
            return []
        
        result = self._extract_json_from_response(response)
        
        if not result:
            return []
        
        violations_data = result.get("violations", []) if isinstance(result, dict) else []
        
        violations = []
        for v_data in violations_data:
            try:
                severity_str = v_data.get("severity", "warning")
                severity = ViolationSeverity(severity_str) if severity_str in ["error", "warning", "info"] else ViolationSeverity.WARNING
                
                violation = Violation.create(
                    rule_id=v_data.get("rule_id", "ai-detected"),
                    rule_type=v_data.get("rule_type", "ai-validation"),
                    severity=severity,
                    message=v_data.get("message", "AI-detected violation"),
                    file_path=file_path,
                    line_number=v_data.get("line_number"),
                    suggestion=v_data.get("suggestion"),
                )
                violations.append(violation)
            except Exception as e:
                logger.warning(f"Failed to parse AI violation: {e}")
        
        return violations
    
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
