"""API routes for architecture configuration and validation."""
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel


router = APIRouter(prefix="/architecture", tags=["architecture"])


# Request/Response models
class ArchitectureConfigRequest(BaseModel):
    """Request body for configuring architecture."""
    reference_blueprint_id: Optional[str] = None
    use_learned_architecture: bool = True
    merge_strategy: str = "learned_primary"


class ArchitectureConfigResponse(BaseModel):
    """Response for architecture configuration."""
    repository_id: str
    reference_blueprint_id: Optional[str]
    use_learned_architecture: bool
    merge_strategy: str


class ValidateCodeRequest(BaseModel):
    """Request body for code validation."""
    file_path: str
    code_content: str


class ValidateCodeResponse(BaseModel):
    """Response for code validation."""
    file_path: str
    is_valid: bool
    violations: list[dict[str, Any]]
    rules_checked: int


class CheckLocationRequest(BaseModel):
    """Request body for file location check."""
    file_path: str


class CheckLocationResponse(BaseModel):
    """Response for file location check."""
    file_path: str
    is_valid: bool
    violations: list[dict[str, Any]]
    suggestion: Optional[str] = None


class ImplementationGuideResponse(BaseModel):
    """Response for implementation guide."""
    feature_type: str
    steps: list[str]
    file_locations: list[dict[str, str]]
    patterns_to_use: list[dict[str, str]]


class AgentFilesResponse(BaseModel):
    """Response for agent files."""
    claude_md: str
    cursor_rules: str
    agents_md: str


# Dependency to get services
# In a real implementation, these would be injected via dependency injection
_resolver = None
_validator = None
_generator = None


def get_resolver():
    """Get architecture resolver."""
    if _resolver is None:
        raise HTTPException(status_code=503, detail="Architecture resolver not configured")
    return _resolver


def get_validator():
    """Get architecture validator."""
    if _validator is None:
        raise HTTPException(status_code=503, detail="Architecture validator not configured")
    return _validator


def get_generator():
    """Get agent file generator."""
    if _generator is None:
        raise HTTPException(status_code=503, detail="Agent file generator not configured")
    return _generator


def configure_services(resolver, validator, generator):
    """Configure services for the routes."""
    global _resolver, _validator, _generator
    _resolver = resolver
    _validator = validator
    _generator = generator


# Routes
@router.get("/repositories/{repository_id}")
async def get_architecture(
    repository_id: str,
    section: Optional[str] = None,
    resolver=Depends(get_resolver),
) -> dict[str, Any]:
    """Get resolved architecture for a repository.
    
    Args:
        repository_id: Repository ID
        section: Optional section filter (layers, patterns, locations, principles, dependencies)
    
    Returns:
        Resolved architecture rules
    """
    try:
        architecture = await resolver.get_rules_for_repository(repository_id)
        
        if section and section != "all":
            section_to_type = {
                "layers": "layer",
                "patterns": "pattern",
                "locations": "location",
                "principles": "principle",
                "dependencies": "dependency",
                "conventions": "convention",
                "boundaries": "boundary",
            }
            
            rule_type = section_to_type.get(section)
            if rule_type:
                rules = architecture.get_rules_by_type(rule_type)
                return {
                    "repository_id": repository_id,
                    "section": section,
                    "rules_count": len(rules),
                    "rules": [r.to_dict() for r in rules],
                }
        
        return architecture.to_dict()
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/repositories/{repository_id}/config")
async def configure_architecture(
    repository_id: str,
    request: ArchitectureConfigRequest,
    resolver=Depends(get_resolver),
) -> ArchitectureConfigResponse:
    """Configure architecture sources for a repository.
    
    Args:
        repository_id: Repository ID
        request: Configuration request
    
    Returns:
        Updated configuration
    """
    try:
        config = await resolver.configure_repository(
            repository_id=repository_id,
            reference_blueprint_id=request.reference_blueprint_id,
            use_learned_architecture=request.use_learned_architecture,
            merge_strategy=request.merge_strategy,
        )
        
        return ArchitectureConfigResponse(
            repository_id=config.repository_id,
            reference_blueprint_id=config.reference_blueprint_id,
            use_learned_architecture=config.use_learned_architecture,
            merge_strategy=config.merge_strategy,
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/repositories/{repository_id}/validate")
async def validate_code(
    repository_id: str,
    request: ValidateCodeRequest,
    validator=Depends(get_validator),
) -> ValidateCodeResponse:
    """Validate code against architecture rules.
    
    Args:
        repository_id: Repository ID
        request: Validation request with file path and code
    
    Returns:
        Validation result
    """
    try:
        result = await validator.validate_file(
            repository_id=repository_id,
            file_path=request.file_path,
            content=request.code_content,
        )
        
        return ValidateCodeResponse(
            file_path=result.file_path,
            is_valid=result.is_valid,
            violations=[v.to_dict() for v in result.violations],
            rules_checked=result.rules_checked,
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/repositories/{repository_id}/check-location")
async def check_file_location(
    repository_id: str,
    request: CheckLocationRequest,
    validator=Depends(get_validator),
) -> CheckLocationResponse:
    """Check if a file path follows architecture conventions.
    
    Args:
        repository_id: Repository ID
        request: Location check request
    
    Returns:
        Location check result
    """
    try:
        result = await validator.check_file_location(
            repository_id=repository_id,
            file_path=request.file_path,
        )
        
        suggestion = result.violations[0].suggestion if result.violations else None
        
        return CheckLocationResponse(
            file_path=result.file_path,
            is_valid=result.is_valid,
            violations=[v.to_dict() for v in result.violations],
            suggestion=suggestion,
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/repositories/{repository_id}/guide/{feature_type}")
async def get_implementation_guide(
    repository_id: str,
    feature_type: str,
    resolver=Depends(get_resolver),
) -> ImplementationGuideResponse:
    """Get implementation guide for a feature type.
    
    Args:
        repository_id: Repository ID
        feature_type: Type of feature (e.g., api_endpoint, service, entity)
    
    Returns:
        Implementation guide
    """
    try:
        architecture = await resolver.get_rules_for_repository(repository_id)
        
        guide = {
            "feature_type": feature_type,
            "steps": [],
            "file_locations": [],
            "patterns_to_use": [],
        }
        
        # Build guide from rules
        type_lower = feature_type.lower()
        
        for rule in architecture.get_rules_by_type("location"):
            purpose = rule.rule_data.get("purpose", "").lower()
            path = rule.rule_data.get("path", "")
            if type_lower in purpose or type_lower in path.lower():
                guide["file_locations"].append({
                    "path": path,
                    "purpose": rule.rule_data.get("purpose", ""),
                })
        
        for rule in architecture.get_pattern_rules():
            if type_lower in rule.name.lower() or type_lower in (rule.description or "").lower():
                guide["patterns_to_use"].append({
                    "pattern": rule.name,
                    "description": rule.description or "",
                })
        
        # Build steps
        if guide["file_locations"]:
            guide["steps"].append(f"1. Create file in: {guide['file_locations'][0]['path']}")
        if guide["patterns_to_use"]:
            guide["steps"].append(f"2. Follow pattern: {guide['patterns_to_use'][0]['pattern']}")
        
        return ImplementationGuideResponse(**guide)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/repositories/{repository_id}/agent-files")
async def get_agent_files(
    repository_id: str,
    repository_name: Optional[str] = None,
    resolver=Depends(get_resolver),
    generator=Depends(get_generator),
) -> AgentFilesResponse:
    """Get generated agent instruction files.
    
    Args:
        repository_id: Repository ID
        repository_name: Optional human-readable name
    
    Returns:
        Generated CLAUDE.md, Cursor rules, and AGENTS.md
    """
    try:
        architecture = await resolver.get_rules_for_repository(repository_id)
        name = repository_name or repository_id
        
        claude_md = await generator.generate_claude_md(
            repository_id=repository_id,
            repository_name=name,
            architecture=architecture,
        )
        
        cursor_rules = await generator.generate_cursor_rules(
            repository_name=name,
            architecture=architecture,
        )
        
        agents_md = await generator.generate_agents_md(
            repository_name=name,
            architecture=architecture,
        )
        
        return AgentFilesResponse(
            claude_md=claude_md,
            cursor_rules=cursor_rules,
            agents_md=agents_md,
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reference-blueprints")
async def list_reference_blueprints(
    resolver=Depends(get_resolver),
) -> dict[str, Any]:
    """List available reference architecture blueprints.
    
    Returns:
        List of blueprint IDs
    """
    try:
        blueprints = await resolver._architecture_rule_repo.list_blueprints()
        
        return {
            "blueprints": blueprints,
            "count": len(blueprints),
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
