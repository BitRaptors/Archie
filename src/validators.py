"""Validation logic for architectural compliance checking."""

from typing import Dict, List, Literal, Tuple

from .utils.patterns import (
    BACKEND_LAYER_RULES,
    FRONTEND_STRUCTURE_RULES,
    check_file_placement,
    check_layer_violations,
    detect_patterns,
)


def validate_layer_compliance(
    code: str, layer: Literal["presentation", "application", "domain", "infrastructure"]
) -> Dict[str, any]:
    """Validate code against layer rules.
    
    Returns:
        Dict with is_valid, violations, and suggestions
    """
    violations = check_layer_violations(code, layer)
    
    suggestions = []
    for violation_type, message in violations:
        if violation_type == "forbidden_import":
            suggestions.append(
                f"Remove the forbidden import. Consider using dependency injection "
                f"to access infrastructure services through interfaces defined in the domain layer."
            )
    
    return {
        "is_valid": len(violations) == 0,
        "violations": [{"type": v[0], "message": v[1]} for v in violations],
        "suggestions": suggestions,
        "layer": layer,
        "rules": BACKEND_LAYER_RULES.get(layer, {}).get("description", "")
    }


def validate_file_structure(file_path: str, stack: Literal["backend", "frontend"]) -> Dict[str, any]:
    """Validate file placement against structure conventions.
    
    Returns:
        Dict with is_valid and issues
    """
    is_valid, issues = check_file_placement(file_path, stack)
    
    suggestions = []
    if not is_valid:
        if stack == "frontend":
            suggestions.append(
                "Review the frontend structure guide. Files should be organized by purpose: "
                "hooks/ for custom hooks, components/ for UI, context/ for global state, etc."
            )
    
    return {
        "is_valid": is_valid,
        "issues": issues,
        "suggestions": suggestions,
        "file_path": file_path,
        "stack": stack
    }


def review_component(
    code: str,
    component_type: str,
    stack: Literal["backend", "frontend"]
) -> Dict[str, any]:
    """Review code for architectural compliance.
    
    Returns:
        Dict with compliance_score, issues, and suggestions
    """
    detected_patterns = detect_patterns(code, stack)
    issues = []
    suggestions = []
    score = 100
    
    if stack == "backend":
        # Check for common violations
        if "from fastapi import" in code and component_type == "service":
            issues.append("Service should not import FastAPI directly")
            suggestions.append("Move HTTP concerns to the presentation layer (controllers)")
            score -= 20
        
        if "from supabase import" in code and component_type == "domain":
            issues.append("Domain layer should not import Supabase")
            suggestions.append("Use repository interfaces defined in domain/interfaces")
            score -= 30
        
        # Check for good patterns
        if detected_patterns.get("repository_interface"):
            suggestions.append("✓ Good: Using repository interface pattern")
        
        if detected_patterns.get("domain_entity"):
            suggestions.append("✓ Good: Using domain entity pattern")
    
    elif stack == "frontend":
        # Check for common violations
        if "import { firebase" in code and "use" in component_type.lower():
            issues.append("Hook should use service abstraction, not direct Firebase import")
            suggestions.append("Use useAuthService() or similar from context/services")
            score -= 20
        
        if "useState" in code and "useQuery" in code and component_type == "hook":
            issues.append("Mixing local state with server state in same hook")
            suggestions.append("Separate concerns: useQuery for server state, useState for local state")
            score -= 15
        
        # Check for good patterns
        if detected_patterns.get("context_provider"):
            suggestions.append("✓ Good: Using Context Provider pattern")
        
        if detected_patterns.get("query_hook"):
            suggestions.append("✓ Good: Using TanStack Query for server state")
    
    return {
        "compliance_score": max(0, score),
        "issues": issues,
        "suggestions": suggestions,
        "detected_patterns": {k: v for k, v in detected_patterns.items() if v},
        "component_type": component_type,
        "stack": stack
    }


