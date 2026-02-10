"""Structured blueprint schema for architecture warden.

This module defines the Pydantic models for the dual-format blueprint output.
The structured JSON is the single source of truth from which all outputs
(markdown, CLAUDE.md, Cursor rules, MCP tools) are derived.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field


# ── Meta ──────────────────────────────────────────────────────────────────────

class ConfidenceScores(BaseModel):
    """Per-section confidence scores (0.0 – 1.0)."""
    architecture_rules: float = 0.0
    decisions: float = 0.0
    components: float = 0.0
    communication: float = 0.0
    technology: float = 0.0


class BlueprintMeta(BaseModel):
    """Metadata about the analysis that produced this blueprint."""
    repository: str = ""
    repository_id: str = ""
    analyzed_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    schema_version: str = "1.0.0"
    architecture_style: str = ""
    confidence: ConfidenceScores = Field(default_factory=ConfidenceScores)


# ── Architecture Rules (enforceable) ─────────────────────────────────────────

class DependencyConstraint(BaseModel):
    """A single enforceable dependency / import rule."""
    source_pattern: str = ""
    source_description: str = ""
    allowed_imports: list[str] = Field(default_factory=list)
    forbidden_imports: list[str] = Field(default_factory=list)
    severity: str = "error"  # error | warning | info
    rationale: str = ""


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
    examples: list[str] = Field(default_factory=list)
    description: str = ""


class ArchitectureRules(BaseModel):
    """Enforceable architecture rules extracted from the codebase."""
    dependency_constraints: list[DependencyConstraint] = Field(default_factory=list)
    file_placement_rules: list[FilePlacementRule] = Field(default_factory=list)
    naming_conventions: list[NamingConvention] = Field(default_factory=list)


# ── Decisions (ADRs) ─────────────────────────────────────────────────────────

class ArchitecturalDecision(BaseModel):
    """A key architectural decision."""
    title: str = ""
    chosen: str = ""
    rationale: str = ""
    alternatives_rejected: list[str] = Field(default_factory=list)


class TradeOff(BaseModel):
    """An accepted trade-off."""
    accept: str = ""
    benefit: str = ""


class Decisions(BaseModel):
    """Architectural decisions and trade-offs."""
    architectural_style: ArchitecturalDecision = Field(default_factory=ArchitecturalDecision)
    key_decisions: list[ArchitecturalDecision] = Field(default_factory=list)
    trade_offs: list[TradeOff] = Field(default_factory=list)
    out_of_scope: list[str] = Field(default_factory=list)


# ── Components ────────────────────────────────────────────────────────────────

class KeyInterface(BaseModel):
    """A key interface / contract within a component."""
    name: str = ""
    methods: list[str] = Field(default_factory=list)
    description: str = ""


class Component(BaseModel):
    """An architectural component (layer, module, feature slice, etc.)."""
    name: str = ""
    location: str = ""
    responsibility: str = ""
    depends_on: list[str] = Field(default_factory=list)
    exposes_to: list[str] = Field(default_factory=list)
    key_interfaces: list[KeyInterface] = Field(default_factory=list)
    key_files: list[dict[str, str]] = Field(default_factory=list)


class Contract(BaseModel):
    """An interface contract between components."""
    interface_name: str = ""
    description: str = ""
    methods: list[str] = Field(default_factory=list)
    properties: list[str] = Field(default_factory=list)
    implementing_files: list[str] = Field(default_factory=list)


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
    examples: list[str] = Field(default_factory=list)


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


# ── Top-Level Blueprint ──────────────────────────────────────────────────────

class StructuredBlueprint(BaseModel):
    """The complete structured blueprint — single source of truth.

    All outputs (markdown, CLAUDE.md, Cursor rules, MCP queries) are
    derived from this model.
    """
    meta: BlueprintMeta = Field(default_factory=BlueprintMeta)
    architecture_rules: ArchitectureRules = Field(default_factory=ArchitectureRules)
    decisions: Decisions = Field(default_factory=Decisions)
    components: Components = Field(default_factory=Components)
    communication: Communication = Field(default_factory=Communication)
    quick_reference: QuickReference = Field(default_factory=QuickReference)
    technology: Technology = Field(default_factory=Technology)
