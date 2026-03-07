"""Structured blueprint schema for architecture warden.

This module defines the Pydantic models for the unified blueprint output.
The structured JSON is the single source of truth from which all outputs
(markdown, CLAUDE.md, Cursor rules, MCP tools) are derived.

The schema is platform-agnostic: it captures backend, frontend, mobile,
and full-stack applications in a single unified blueprint.
"""
from __future__ import annotations

from datetime import datetime, timezone

from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, Field, field_validator


def _coerce_str_list(v: Any) -> list[str]:
    """Coerce a list that may contain dicts (from AI output) into list[str].

    The AI model sometimes returns structured objects like
    {"name": "RxSwift", "version": "unspecified"} or
    {"name": "title", "type": "String", "description": "..."} instead of
    plain strings. This validator normalizes them.
    """
    if not isinstance(v, list):
        return []
    result: list[str] = []
    for item in v:
        if isinstance(item, str):
            result.append(item)
        elif isinstance(item, dict):
            # Try common key patterns first
            name = item.get("name", item.get("title", ""))
            extra = item.get("version", item.get("type", item.get("description", "")))
            if name and extra and extra not in ("unspecified", ""):
                result.append(f"{name} {extra}")
            elif name:
                result.append(name)
            else:
                # Flatten dict values into readable string
                parts = []
                for k, val in item.items():
                    if isinstance(val, list):
                        parts.append(f"{k}: {', '.join(str(x) for x in val)}")
                    elif val:
                        parts.append(f"{k}: {val}")
                result.append("; ".join(parts))
        else:
            result.append(str(item))
    return result


StrList = Annotated[list[str], BeforeValidator(_coerce_str_list)]


def _coerce_to_str(v: Any) -> str:
    """Coerce non-string values (list, dict) from AI output into a flat string.

    The AI sometimes returns structured objects for fields declared as str.
    E.g. a list of dicts for serverless_functions or a nested dict for
    environment_config.  This validator flattens them into a readable string.
    """
    if isinstance(v, str):
        return v
    if isinstance(v, list):
        parts = []
        for item in v:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                name = item.get("name", item.get("service", ""))
                desc = item.get("description", item.get("purpose", ""))
                parts.append(f"{name}: {desc}" if name and desc else name or str(item))
            else:
                parts.append(str(item))
        return "; ".join(parts)
    if isinstance(v, dict):
        parts = []
        for k, val in v.items():
            if isinstance(val, list):
                parts.append(f"{k}: {', '.join(str(x) for x in val)}")
            else:
                parts.append(f"{k}: {val}")
        return "; ".join(parts)
    return str(v) if v else ""


CoercedStr = Annotated[str, BeforeValidator(_coerce_to_str)]


# ── Meta ──────────────────────────────────────────────────────────────────────

class ConfidenceScores(BaseModel):
    """Per-section confidence scores (0.0 – 1.0)."""
    architecture_rules: float = 0.0
    decisions: float = 0.0
    components: float = 0.0
    communication: float = 0.0
    technology: float = 0.0
    frontend: float = 0.0
    deployment: float = 0.0


class BlueprintMeta(BaseModel):
    """Metadata about the analysis that produced this blueprint."""
    repository: str = ""
    repository_id: str = ""
    analyzed_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    schema_version: str = "2.0.0"
    architecture_style: str = ""
    platforms: StrList = Field(default_factory=list)  # e.g. ["backend", "web-frontend", "mobile-ios"]
    executive_summary: str = ""  # 3-5 factual sentences about the codebase
    confidence: ConfidenceScores = Field(default_factory=ConfidenceScores)


# ── Architecture Rules (enforceable) ─────────────────────────────────────────

class FilePlacementRule(BaseModel):
    """Where a certain kind of file should live."""
    component_type: str = ""
    naming_pattern: str = ""
    location: str = ""
    example: str = ""
    description: str = ""


class NamingConvention(BaseModel):
    """A naming convention observed in the codebase."""
    scope: str = ""  # classes | functions | files | modules | variables
    pattern: str = ""
    examples: StrList = Field(default_factory=list)
    description: str = ""


class ArchitectureRules(BaseModel):
    """Enforceable architecture rules extracted from the codebase."""
    file_placement_rules: list[FilePlacementRule] = Field(default_factory=list)
    naming_conventions: list[NamingConvention] = Field(default_factory=list)


# ── Decisions (ADRs) ─────────────────────────────────────────────────────────

class ArchitecturalDecision(BaseModel):
    """A key architectural decision."""
    title: str = ""
    chosen: str = ""
    rationale: str = ""
    alternatives_rejected: StrList = Field(default_factory=list)


class TradeOff(BaseModel):
    """An accepted trade-off."""
    accept: str = ""
    benefit: str = ""


class Decisions(BaseModel):
    """Architectural decisions and trade-offs."""
    architectural_style: ArchitecturalDecision = Field(default_factory=ArchitecturalDecision)
    key_decisions: list[ArchitecturalDecision] = Field(default_factory=list)
    trade_offs: list[TradeOff] = Field(default_factory=list)
    out_of_scope: StrList = Field(default_factory=list)


# ── Components ────────────────────────────────────────────────────────────────

class KeyInterface(BaseModel):
    """A key interface / contract within a component."""
    name: str = ""
    methods: StrList = Field(default_factory=list)
    description: str = ""


class Component(BaseModel):
    """An architectural component (layer, module, feature slice, etc.)."""
    name: str = ""
    location: str = ""
    responsibility: str = ""
    platform: str = ""  # backend | frontend | shared | ""
    depends_on: StrList = Field(default_factory=list)
    exposes_to: StrList = Field(default_factory=list)
    key_interfaces: list[KeyInterface] = Field(default_factory=list)
    key_files: list[dict[str, str]] = Field(default_factory=list)


class Contract(BaseModel):
    """An interface contract between components."""
    interface_name: str = ""
    description: str = ""
    methods: StrList = Field(default_factory=list)
    properties: StrList = Field(default_factory=list)
    implementing_files: StrList = Field(default_factory=list)


class Components(BaseModel):
    """All architectural components and their contracts."""
    structure_type: str = ""  # layered | modular | feature-based | flat | other
    components: list[Component] = Field(default_factory=list)
    contracts: list[Contract] = Field(default_factory=list)


# ── Communication ─────────────────────────────────────────────────────────────

class CommunicationPattern(BaseModel):
    """A communication pattern used in the codebase."""
    name: str = ""
    when_to_use: str = ""
    how_it_works: str = ""
    examples: StrList = Field(default_factory=list)


class Integration(BaseModel):
    """A third-party integration."""
    service: str = ""
    purpose: str = ""
    integration_point: str = ""


class PatternGuideline(BaseModel):
    """When to pick which communication pattern."""
    scenario: str = ""
    pattern: str = ""
    rationale: str = ""


class Communication(BaseModel):
    """Communication patterns and integrations."""
    patterns: list[CommunicationPattern] = Field(default_factory=list)
    integrations: list[Integration] = Field(default_factory=list)
    pattern_selection_guide: list[PatternGuideline] = Field(default_factory=list)


# ── Quick Reference ───────────────────────────────────────────────────────────

class ErrorMapping(BaseModel):
    """Maps domain errors to status/exit codes."""
    error: str = ""
    status_code: int | str = ""
    description: str = ""


class QuickReference(BaseModel):
    """Lookup tables for common questions."""
    where_to_put_code: dict[str, str] = Field(default_factory=dict)
    pattern_selection: dict[str, str] = Field(default_factory=dict)
    error_mapping: list[ErrorMapping] = Field(default_factory=list)


# ── Technology ────────────────────────────────────────────────────────────────

class TechStackEntry(BaseModel):
    """A single technology in the stack."""
    category: str = ""  # runtime | framework | database | cache | queue | ai | auth | testing | ...
    name: str = ""
    version: str = ""
    purpose: str = ""


class CodeTemplate(BaseModel):
    """A code template / boilerplate for a common component type."""
    component_type: str = ""
    description: str = ""
    file_path_template: str = ""
    code: str = ""


class Technology(BaseModel):
    """Technology stack and code templates."""
    stack: list[TechStackEntry] = Field(default_factory=list)
    templates: list[CodeTemplate] = Field(default_factory=list)
    project_structure: str = ""  # ASCII directory tree
    run_commands: dict[str, str] = Field(default_factory=dict)  # dev, test, prod, worker


# ── Frontend ─────────────────────────────────────────────────────────────────

class UIComponent(BaseModel):
    """A UI component or page in the frontend."""
    name: str = ""
    location: str = ""
    component_type: str = ""  # page | layout | feature | shared | primitive
    description: str = ""
    props: StrList = Field(default_factory=list)
    children: StrList = Field(default_factory=list)


class StateManagement(BaseModel):
    """How state is managed in the frontend."""
    approach: str = ""  # e.g. "React Query + Context", "Redux Toolkit", "Zustand"
    global_state: list[dict[str, Any]] = Field(default_factory=list)
    server_state: str = ""  # e.g. "TanStack Query", "SWR", "Apollo"
    local_state: str = ""  # e.g. "useState", "useReducer"
    rationale: str = ""

    @field_validator("local_state", mode="before")
    @classmethod
    def _coerce_local_state(cls, v: Any) -> str:
        """Coerce AI output into str.

        The AI sometimes returns a list of strings instead of a single string.
        """
        if isinstance(v, list):
            return "; ".join(str(item) for item in v)
        return v

    @field_validator("global_state", mode="before")
    @classmethod
    def _coerce_global_state(cls, v: Any) -> list[dict[str, Any]]:
        """Coerce AI output into list[dict].

        The AI sometimes returns plain strings (e.g. for mobile projects)
        instead of the expected [{"store": "...", "purpose": "..."}] format.
        """
        if not isinstance(v, list):
            return []
        result: list[dict[str, Any]] = []
        for item in v:
            if isinstance(item, dict):
                result.append(item)
            elif isinstance(item, str):
                result.append({"description": item})
            else:
                result.append({"description": str(item)})
        return result


class Route(BaseModel):
    """A frontend route / page."""
    path: str = ""
    component: str = ""
    description: str = ""
    auth_required: bool = False


class DataFetchingPattern(BaseModel):
    """A data fetching pattern used in the frontend."""
    name: str = ""
    mechanism: str = ""  # e.g. "React Query hook", "fetch in loader", "SSR getServerSideProps"
    when_to_use: str = ""
    examples: StrList = Field(default_factory=list)


class Frontend(BaseModel):
    """Frontend-specific architecture details.

    Populated when the codebase contains a web or mobile frontend.
    Left empty for backend-only projects.
    """
    framework: str = ""  # e.g. "Next.js 14", "React Native 0.73", "Vue 3"
    rendering_strategy: str = ""  # SSR | SSG | CSR | ISR | hybrid
    ui_components: list[UIComponent] = Field(default_factory=list)
    state_management: StateManagement = Field(default_factory=StateManagement)
    routing: list[Route] = Field(default_factory=list)
    data_fetching: list[DataFetchingPattern] = Field(default_factory=list)
    styling: str = ""  # e.g. "Tailwind CSS", "CSS Modules", "Styled Components"
    key_conventions: StrList = Field(default_factory=list)


# ── Developer Guidance ────────────────────────────────────────────────────────

class DeveloperRecipe(BaseModel):
    """Actionable recipe: 'To do X, touch these files and follow these steps.'"""
    task: str = ""
    files: StrList = Field(default_factory=list)
    steps: StrList = Field(default_factory=list)


class ArchitecturalPitfall(BaseModel):
    """A non-obvious behavior, edge case, or common mistake in the codebase."""
    area: str = ""
    description: str = ""
    recommendation: str = ""


class DeploymentEnvironment(BaseModel):
    """Where and how the application is deployed/distributed.

    Covers cloud-hosted services, mobile app stores, package registries,
    desktop distribution, embedded targets, and self-hosted setups.
    """
    runtime_environment: CoercedStr = ""       # "Google Cloud Platform", "AWS", "on-device (iOS/Android)", "browser", "self-hosted"
    compute_services: StrList = Field(default_factory=list)    # "Cloud Run", "App Engine", "Lambda", "Vercel"
    container_runtime: CoercedStr = ""         # "Docker", "Podman", ""
    orchestration: CoercedStr = ""             # "Kubernetes", "Docker Compose", "ECS", ""
    serverless_functions: CoercedStr = ""      # "Cloud Functions", "Lambda", "Edge Functions", ""
    ci_cd: StrList = Field(default_factory=list)               # "GitHub Actions", "Cloud Build", "Fastlane"
    distribution: StrList = Field(default_factory=list)        # "App Store", "Google Play", "npm registry", "Docker Hub"
    infrastructure_as_code: CoercedStr = ""    # "Terraform", "CloudFormation", "Pulumi", ""
    supporting_services: StrList = Field(default_factory=list) # "Firebase", "Supabase", "Redis Cloud"
    environment_config: CoercedStr = ""        # "env files per stage", "GCP Secret Manager", "SSM Parameter Store"
    key_files: StrList = Field(default_factory=list)           # "Dockerfile", "app.yaml", ".github/workflows/deploy.yml"


class DevelopmentRule(BaseModel):
    """Imperative development rule extracted from codebase signals."""
    category: str = ""   # dependency_management, testing, code_style, ci_cd, environment, git
    rule: str = ""       # "Always use poetry for dependency management"
    source: str = ""     # "pyproject.toml uses [tool.poetry]"


class ImplementationGuideline(BaseModel):
    """How an existing capability was implemented — replication guide for agents."""
    capability: str = ""          # "Push Notifications", "Map Display"
    category: str = ""            # "notifications", "location", "media", "auth", "persistence", "ui"
    libraries: StrList = Field(default_factory=list)  # ["Firebase Cloud Messaging 10.x"]
    pattern_description: str = "" # 1-3 sentences: how it was built
    key_files: StrList = Field(default_factory=list)  # actual file paths
    usage_example: str = ""       # code snippet or invocation pattern
    tips: StrList = Field(default_factory=list)        # gotchas for this capability


# ── Top-Level Blueprint ──────────────────────────────────────────────────────

class StructuredBlueprint(BaseModel):
    """The complete structured blueprint — single source of truth.

    All outputs (markdown, CLAUDE.md, Cursor rules, MCP queries) are
    derived from this model. Supports backend, frontend, and full-stack
    applications in a single unified schema.
    """
    meta: BlueprintMeta = Field(default_factory=BlueprintMeta)
    architecture_rules: ArchitectureRules = Field(default_factory=ArchitectureRules)
    decisions: Decisions = Field(default_factory=Decisions)
    components: Components = Field(default_factory=Components)
    communication: Communication = Field(default_factory=Communication)
    quick_reference: QuickReference = Field(default_factory=QuickReference)
    technology: Technology = Field(default_factory=Technology)
    frontend: Frontend = Field(default_factory=Frontend)
    developer_recipes: list[DeveloperRecipe] = Field(default_factory=list)
    architecture_diagram: str = ""  # Mermaid graph TD syntax
    pitfalls: list[ArchitecturalPitfall] = Field(default_factory=list)
    implementation_guidelines: list[ImplementationGuideline] = Field(default_factory=list)
    development_rules: list[DevelopmentRule] = Field(default_factory=list)
    deployment: DeploymentEnvironment = Field(default_factory=DeploymentEnvironment)
