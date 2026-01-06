"""Pattern matching utilities for validation."""

import re
from typing import Dict, List, Tuple


# Backend layer rules
BACKEND_LAYER_RULES: Dict[str, Dict[str, List[str]]] = {
    "domain": {
        "forbidden_imports": [
            "fastapi", "supabase", "redis", "openai", "google.generativeai",
            "requests", "httpx", "sse_starlette", "arq", "gunicorn", "uvicorn"
        ],
        "description": "Domain layer must have no external dependencies"
    },
    "application": {
        "forbidden_imports": [
            "fastapi", "Request", "Response", "APIRouter", "HTTPException"
        ],
        "description": "Application layer should not know about HTTP"
    },
    "presentation": {
        "allowed_imports": [
            "fastapi", "pydantic", "Request", "Response"
        ],
        "description": "Presentation layer handles HTTP concerns"
    },
    "infrastructure": {
        "allowed_imports": [
            "supabase", "redis", "openai", "google.generativeai", "requests", "httpx"
        ],
        "description": "Infrastructure layer integrates with external systems"
    }
}

# Frontend structure rules
FRONTEND_STRUCTURE_RULES: Dict[str, str] = {
    "hooks/api/": "Should contain TanStack Query hooks (useQuery, useMutation)",
    "context/": "Should contain React Context + Provider",
    "components/atoms/": "Should contain shadcn/ui primitives",
    "components/molecules/": "Should contain composed components",
    "services/": "Should contain plain functions, not classes",
    "types/": "Should contain TypeScript type definitions",
    "utils/": "Should contain utility functions and query key factories"
}

# Pattern detection regexes
BACKEND_PATTERNS = {
    "repository_interface": r"class\s+I\w+Repository.*ABC",
    "service_class": r"class\s+\w+Service:",
    "controller_function": r"@router\.(get|post|put|patch|delete)",
    "domain_entity": r"@dataclass\s+class\s+\w+.*:",
}

FRONTEND_PATTERNS = {
    "context_provider": r"export\s+(const|function)\s+\w+Provider",
    "custom_hook": r"export\s+(const|function)\s+use\w+",
    "query_hook": r"useQuery\s*\(",
    "mutation_hook": r"useMutation\s*\(",
    "service_interface": r"export\s+interface\s+I\w+Service",
}


def check_layer_violations(code: str, layer: str) -> List[Tuple[str, str]]:
    """Check for layer boundary violations in code.
    
    Returns:
        List of (violation_type, message) tuples
    """
    violations = []
    
    if layer not in BACKEND_LAYER_RULES:
        return violations
    
    rules = BACKEND_LAYER_RULES[layer]
    forbidden = rules.get("forbidden_imports", [])
    
    # Check for forbidden imports
    for forbidden_import in forbidden:
        # Match import statements
        pattern = rf"^\s*(import|from)\s+{re.escape(forbidden_import)}"
        if re.search(pattern, code, re.MULTILINE):
            violations.append((
                "forbidden_import",
                f"Layer '{layer}' should not import '{forbidden_import}'. {rules.get('description', '')}"
            ))
    
    return violations


def check_file_placement(file_path: str, stack: str) -> Tuple[bool, List[str]]:
    """Check if file path follows structure conventions.
    
    Returns:
        Tuple of (is_valid, list of issues)
    """
    issues = []
    
    if stack == "frontend":
        path_lower = file_path.lower()
        for expected_path, description in FRONTEND_STRUCTURE_RULES.items():
            if expected_path.replace("/", "").replace("_", "") in path_lower:
                # File is in expected location
                return True, []
        
        # Check if it's in a known bad location
        if "components/" in path_lower and "hooks/" in path_lower:
            issues.append("Hooks should not be in components directory")
        if "services/" in path_lower and "context/" in path_lower:
            issues.append("Services should not be in context directory")
    
    return len(issues) == 0, issues


def detect_patterns(code: str, stack: str) -> Dict[str, bool]:
    """Detect architectural patterns in code.
    
    Returns:
        Dict mapping pattern names to whether they were detected
    """
    patterns = FRONTEND_PATTERNS if stack == "frontend" else BACKEND_PATTERNS
    detected = {}
    
    for pattern_name, pattern_regex in patterns.items():
        detected[pattern_name] = bool(re.search(pattern_regex, code, re.MULTILINE))
    
    return detected


