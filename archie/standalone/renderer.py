#!/usr/bin/env python3
"""Archie standalone renderer — generates CLAUDE.md, AGENTS.md, and rule files from blueprint.

Run: python3 renderer.py /path/to/project
Reads: .archie/blueprint.json
Writes: CLAUDE.md, AGENTS.md, .claude/rules/*.md

Zero dependencies beyond Python 3.9+ stdlib.
"""
from __future__ import annotations

import ast
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clean_str_item(item) -> str:
    """Convert any item (str, dict, etc.) to readable text."""
    if isinstance(item, dict):
        # Agent returned a dict — extract meaningful fields
        parts = []
        for k, v in item.items():
            if isinstance(v, list):
                parts.append(f"{k}: {', '.join(str(x) for x in v)}")
            elif v:
                parts.append(f"{k}: {v}")
        return "; ".join(parts) if parts else str(item)
    s = str(item)
    stripped = s.strip()
    if not (stripped.startswith("{") and stripped.endswith("}")):
        return s
    try:
        obj = ast.literal_eval(stripped)
    except (ValueError, SyntaxError):
        return s
    if not isinstance(obj, dict):
        return s
    parts = []
    for k, v in obj.items():
        if isinstance(v, list):
            parts.append(f"{k}: {', '.join(str(x) for x in v)}")
        elif v:
            parts.append(f"{k}: {v}")
    return "; ".join(parts)


def _get(obj, *keys, default=None):
    """Safely traverse nested dicts."""
    current = obj
    for k in keys:
        if isinstance(current, dict):
            current = current.get(k, default)
        else:
            return default
        if current is None:
            return default
    return current


def _as_dict(val, default=None):
    """Ensure a value is a dict. If it's a string, wrap it."""
    if isinstance(val, dict):
        return val
    if default is not None:
        return default
    return {}


def _as_list(val):
    """Ensure a value is a list."""
    if isinstance(val, list):
        return val
    if isinstance(val, str) and val:
        return [val]
    return []


# ---------------------------------------------------------------------------
# Frontend glob detection
# ---------------------------------------------------------------------------

_FRONTEND_GLOB_MAP = {
    "react": ["**/*.tsx", "**/*.jsx"],
    "next": ["**/*.tsx", "**/*.jsx"],
    "vue": ["**/*.vue"],
    "svelte": ["**/*.svelte"],
    "angular": ["**/*.ts", "**/*.html"],
    "flutter": ["**/*.dart"],
    "swiftui": ["**/*.swift"],
    "swift": ["**/*.swift"],
    "kotlin": ["**/*.kt"],
    "react native": ["**/*.tsx", "**/*.jsx"],
}


def _detect_frontend_globs(bp: dict) -> list:
    """Return frontend-specific globs based on framework and tech stack."""
    globs = set()
    fw = (_get(bp, "frontend", "framework", default="") or "").lower()
    for key, patterns in _FRONTEND_GLOB_MAP.items():
        if key in fw:
            globs.update(patterns)
    for entry in _get(bp, "technology", "stack", default=[]) or []:
        name_lower = (entry.get("name", "") or "").lower()
        for key, patterns in _FRONTEND_GLOB_MAP.items():
            if key in name_lower:
                globs.update(patterns)
    return sorted(globs) if globs else ["**/*"]


# ---------------------------------------------------------------------------
# Rule file builders (mirror agent_file_generator.py exactly)
# ---------------------------------------------------------------------------

def _build_architecture_rule(bp: dict):
    """Components, file placement, naming, where-to-put."""
    lines = []

    # Components
    components = _get(bp, "components", "components", default=[]) or []
    if components:
        lines.append("## Components")
        lines.append("")
        for comp in components:
            lines.append(f"### {comp.get('name', '')}")
            lines.append(f"- **Location:** `{comp.get('location', '')}`")
            lines.append(f"- **Responsibility:** {comp.get('responsibility', '')}")
            deps = comp.get("depends_on") or []
            if deps:
                lines.append(f"- **Depends on:** {', '.join(deps)}")
            key_ifaces = comp.get("key_interfaces") or []
            if key_ifaces:
                if isinstance(key_ifaces[0], dict):
                    iface_strs = []
                    for iface in key_ifaces:
                        name = iface.get("name", "")
                        methods = iface.get("methods") or []
                        if methods:
                            iface_strs.append(f"`{name}` ({', '.join(methods)})")
                        else:
                            iface_strs.append(f"`{name}`")
                    lines.append(f"- **Key interfaces:** {', '.join(iface_strs)}")
                elif isinstance(key_ifaces[0], str):
                    lines.append(f"- **Key interfaces:** {', '.join(f'`{i}`' for i in key_ifaces)}")
                else:
                    print(f"Warning: unexpected {type(key_ifaces[0]).__name__} in key_interfaces, coercing", file=sys.stderr)
                    lines.append(f"- **Key interfaces:** {', '.join(f'`{str(i)}`' for i in key_ifaces)}")
            lines.append("")

    # File Placement
    fp_rules = _get(bp, "architecture_rules", "file_placement_rules", default=[]) or []
    if fp_rules:
        lines.append("## File Placement")
        lines.append("")
        lines.append("| Component Type | Location | Naming | Example |")
        lines.append("|---------------|----------|--------|---------|")
        for fp in fp_rules:
            lines.append(
                f"| {fp.get('component_type', '')} | `{fp.get('location', '')}` | `{fp.get('naming_pattern', '')}` | `{fp.get('example', '')}` |"
            )
        lines.append("")

    # Where to Put Code
    where = _get(bp, "quick_reference", "where_to_put_code", default={}) or {}
    if where:
        lines.append("## Where to Put Code")
        lines.append("")
        for comp_type, loc in where.items():
            lines.append(f"- **{comp_type}** -> `{loc}`")
        lines.append("")

    # Naming Conventions
    naming = _get(bp, "architecture_rules", "naming_conventions", default=[]) or []
    if naming:
        lines.append("## Naming Conventions")
        lines.append("")
        for nc in naming:
            examples = ", ".join(f"`{e}`" for e in (nc.get("examples") or [])[:4])
            lines.append(f"- **{nc.get('scope', '')}**: {nc.get('pattern', '')} (e.g. {examples})")
        lines.append("")

    if not lines:
        return None

    return {
        "topic": "architecture",
        "body": "\n".join(lines).rstrip(),
        "description": "Architecture rules: components, file placement, naming conventions",
        "always_apply": True,
        "globs": [],
    }


def _build_patterns_rule(bp: dict):
    """Communication patterns, pattern selection, decisions."""
    lines = []

    # Communication Patterns
    patterns = _get(bp, "communication", "patterns", default=[]) or []
    if patterns:
        lines.append("## Communication Patterns")
        lines.append("")
        for pat in patterns:
            lines.append(f"### {pat.get('name', '')}")
            lines.append(f"- **When:** {pat.get('when_to_use', '')}")
            lines.append(f"- **How:** {pat.get('how_it_works', '')}")
            lines.append("")

    # Pattern Selection Guide
    psg_list = _get(bp, "communication", "pattern_selection_guide", default=[]) or []
    if psg_list:
        lines.append("## Pattern Selection Guide")
        lines.append("")
        lines.append("| Scenario | Pattern | Rationale |")
        lines.append("|----------|---------|-----------|")
        for psg in psg_list:
            lines.append(f"| {psg.get('scenario', '')} | {psg.get('pattern', '')} | {psg.get('rationale', '')} |")
        lines.append("")

    # Quick Reference: Pattern Selection
    ps = _get(bp, "quick_reference", "pattern_selection", default={}) or {}
    if ps:
        lines.append("## Quick Pattern Lookup")
        lines.append("")
        for scenario, pattern in ps.items():
            lines.append(f"- **{scenario}** -> {pattern}")
        lines.append("")

    # Key Decisions
    key_decs = _get(bp, "decisions", "key_decisions", default=[]) or []
    if key_decs:
        lines.append("## Key Decisions")
        lines.append("")
        for dec in key_decs:
            lines.append(f"### {dec.get('title', '')}")
            lines.append(f"**Chosen:** {dec.get('chosen', '')}")
            rationale = dec.get("rationale", "")
            if rationale:
                lines.append(f"**Rationale:** {rationale}")
            alternatives = dec.get("alternatives_rejected") or []
            if alternatives:
                lines.append(f"**Rejected:** {', '.join(alternatives)}")
            forced_by = dec.get("forced_by", "")
            if forced_by:
                lines.append(f"**Forced by:** {forced_by}")
            enables = dec.get("enables", "")
            if enables:
                lines.append(f"**Enables:** {enables}")
            lines.append("")

    # Trade-offs
    trade_offs = _get(bp, "decisions", "trade_offs", default=[]) or []
    if trade_offs:
        lines.append("## Trade-offs Accepted")
        lines.append("")
        lines.append("| Accepted | Benefit | Caused by |")
        lines.append("|----------|---------|-----------|")
        for to in trade_offs:
            accept = to.get("accept", "") or to.get("accepted", "")
            benefit = to.get("benefit", "") or to.get("gained", "")
            caused_by = to.get("caused_by", "")
            lines.append(f"| {accept} | {benefit} | {caused_by} |")
        lines.append("")

    # Out of Scope
    out_of_scope = _get(bp, "decisions", "out_of_scope", default=[]) or []
    if out_of_scope:
        lines.append("## Out of Scope")
        lines.append("")
        for item in out_of_scope:
            lines.append(f"- {item}")
        lines.append("")

    if not lines:
        return None

    return {
        "topic": "patterns",
        "body": "\n".join(lines).rstrip(),
        "description": "Communication and design patterns, key architectural decisions",
        "always_apply": True,
        "globs": [],
    }


def _build_frontend_rule(bp: dict):
    """Frontend architecture rules."""
    fe = _as_dict(bp.get("frontend"))
    has_frontend = fe.get("framework") or fe.get("ui_components") or fe.get("routing") or fe.get("data_fetching")
    if not has_frontend:
        return None

    lines = []
    lines.append("## Frontend Architecture")
    lines.append("")

    if fe.get("framework"):
        lines.append(f"**Framework:** {fe['framework']}")
        lines.append("")
    if fe.get("rendering_strategy"):
        lines.append(f"**Rendering:** {fe['rendering_strategy']}")
        lines.append("")
    if fe.get("styling"):
        lines.append(f"**Styling:** {fe['styling']}")
        lines.append("")

    sm = fe.get("state_management") or {}
    if isinstance(sm, str):
        lines.append(f"**State management:** {sm}")
        lines.append("")
    elif isinstance(sm, dict) and sm.get("approach"):
        lines.append(f"**State management:** {sm['approach']}")
        if sm.get("server_state"):
            lines.append(f"  - Server state: {sm['server_state']}")
        if sm.get("local_state"):
            lines.append(f"  - Local state: {sm['local_state']}")
        lines.append("")

    if fe.get("key_conventions"):
        lines.append("**Conventions:**")
        for conv in fe["key_conventions"]:
            lines.append(f"- {conv}")
        lines.append("")

    globs = _detect_frontend_globs(bp)

    return {
        "topic": "frontend",
        "body": "\n".join(lines).rstrip(),
        "description": "Frontend architecture rules",
        "always_apply": False,
        "globs": globs,
    }


def _build_guidelines_rule(bp: dict):
    """Implementation guidelines."""
    lines = []

    guidelines = bp.get("implementation_guidelines") or []
    if guidelines:
        lines.append("## Implementation Guidelines")
        lines.append("")
        for gl in guidelines:
            if not gl.get("capability"):
                continue
            cat_tag = f" [{gl['category']}]" if gl.get("category") else ""
            lines.append(f"### {gl['capability']}{cat_tag}")
            libs = gl.get("libraries") or []
            if libs:
                lines.append(f"Libraries: {', '.join(f'`{lib}`' for lib in libs)}")
            if gl.get("pattern_description"):
                lines.append(f"Pattern: {gl['pattern_description']}")
            key_files = gl.get("key_files") or []
            if key_files:
                lines.append(f"Key files: {', '.join(f'`{f}`' for f in key_files)}")
            if gl.get("usage_example"):
                lines.append(f"Example: `{gl['usage_example']}`")
            tips = gl.get("tips") or []
            if tips:
                for tip in tips:
                    lines.append(f"- {tip}")
            lines.append("")

    if not lines:
        return None

    return {
        "topic": "guidelines",
        "body": "\n".join(lines).rstrip(),
        "description": "Implementation guidelines for existing capabilities",
        "always_apply": True,
        "globs": [],
    }


def _build_pitfalls_rule(bp: dict):
    """Pitfalls + error mapping."""
    lines = []

    pitfalls = bp.get("pitfalls") or []
    if pitfalls:
        lines.append("## Pitfalls")
        lines.append("")
        for pitfall in pitfalls:
            if not pitfall.get("area") and not pitfall.get("description"):
                continue
            area_label = f"**{pitfall['area']}:** " if pitfall.get("area") else ""
            lines.append(f"- {area_label}{pitfall.get('description', '')}")
            stems = pitfall.get("stems_from")
            if stems:
                if isinstance(stems, list):
                    lines.append(f"  - *causal chain: {" → ".join(stems)}*")
                else:
                    lines.append(f"  - *stems from: {stems}*")
            if pitfall.get("recommendation"):
                lines.append(f"  - *{pitfall['recommendation']}*")
        lines.append("")

    # Error Mapping
    error_mapping = _get(bp, "quick_reference", "error_mapping", default=[]) or []
    if error_mapping:
        lines.append("## Error Mapping")
        lines.append("")
        lines.append("| Error | Status Code |")
        lines.append("|-------|------------|")
        for em in error_mapping:
            lines.append(f"| `{em.get('error', '')}` | {em.get('status_code', '')} |")
        lines.append("")

    if not lines:
        return None

    return {
        "topic": "pitfalls",
        "body": "\n".join(lines).rstrip(),
        "description": "Common pitfalls and error mapping",
        "always_apply": True,
        "globs": [],
    }


def _build_dev_rules_rule(bp: dict):
    """Development rules grouped by category."""
    dev_rules = bp.get("development_rules") or []
    if not dev_rules:
        return None

    by_category = defaultdict(list)
    for dr in dev_rules:
        cat = (dr.get("category") or "").strip() or "general"
        by_category[cat].append(dr)

    lines = []
    lines.append("## Development Rules")
    lines.append("")

    for cat_name in sorted(by_category.keys()):
        heading = cat_name.replace("_", " ").title()
        lines.append(f"### {heading}")
        lines.append("")
        for dr in by_category[cat_name]:
            if dr.get("source"):
                lines.append(f"- {dr.get('rule', '')} *(source: `{dr['source']}`)*")
            else:
                lines.append(f"- {dr.get('rule', '')}")
        lines.append("")

    return {
        "topic": "dev-rules",
        "body": "\n".join(lines).rstrip(),
        "description": "Development rules: imperative do/don't rules from codebase signals",
        "always_apply": True,
        "globs": [],
    }


# ---------------------------------------------------------------------------
# Render rule files with platform-specific frontmatter
# ---------------------------------------------------------------------------

def _render_claude(rule: dict) -> str:
    """Render for Claude Code (.claude/rules/)."""
    globs = rule.get("globs") or []
    if globs:
        globs_yaml = "\n".join(f"  - {g}" for g in globs)
        return f"---\npaths:\n{globs_yaml}\n---\n\n{rule['body']}"
    return rule["body"]




# ---------------------------------------------------------------------------
# CLAUDE.md (lean root file — mirrors generate_claude_md_lean exactly)
# ---------------------------------------------------------------------------

def generate_claude_md(bp: dict) -> str:
    """Generate lean root CLAUDE.md (<120 lines)."""
    timestamp = datetime.now(timezone.utc).isoformat()
    repo = _get(bp, "meta", "repository", default="Unknown Repository") or "Unknown Repository"
    style = (_get(bp, "meta", "architecture_style")
             or _get(bp, "decisions", "architectural_style", "title")
             or "Not determined")

    lines = []

    # Header
    lines.append("# CLAUDE.md")
    lines.append("")
    lines.append(f"> Architecture guidance for **{repo}**")
    lines.append(f"> Style: {style}")
    lines.append(f"> Generated: {timestamp}")
    lines.append("")

    # Executive Summary
    summary = _get(bp, "meta", "executive_summary")
    if summary:
        lines.append("## Overview")
        lines.append("")
        lines.append(summary)
        lines.append("")

    # Architecture style
    ad = _get(bp, "decisions", "architectural_style", default={}) or {}
    if ad.get("chosen"):
        lines.append("## Architecture")
        lines.append("")
        lines.append(f"**Style:** {ad['chosen']}")
        structure = _get(bp, "components", "structure_type")
        if structure:
            lines.append(f"**Structure:** {structure}")
        if ad.get("rationale"):
            lines.append("")
            lines.append(ad["rationale"])
        lines.append("")

    # Decision chain (compact — root + top-level forces)
    dc = _get(bp, "decisions", "decision_chain", default={}) or {}
    if dc.get("root"):
        lines.append(f"**Root constraint:** {dc['root']}")
        for f in (dc.get("forces") or [])[:5]:
            lines.append(f"- → {f.get('decision', '')}")
        lines.append("")

    # Trade-offs summary (top 3)
    trade_offs = _get(bp, "decisions", "trade_offs", default=[]) or []
    if trade_offs:
        lines.append("**Key trade-offs:**")
        for to in trade_offs[:3]:
            accept = to.get("accept", "") or to.get("accepted", "")
            benefit = to.get("benefit", "") or to.get("gained", "")
            lines.append(f"- {accept} → {benefit}")
        lines.append("")

    # Deployment
    dep = _as_dict(bp.get("deployment"))
    if dep.get("runtime_environment"):
        lines.append(f"**Runs on:** {dep['runtime_environment']}")
        if dep.get("compute_services"):
            lines.append(f"**Compute:** {', '.join(_as_list(dep['compute_services']))}")
        if dep.get("ci_cd"):
            cleaned = [_clean_str_item(x) for x in dep["ci_cd"]]
            lines.append(f"**CI/CD:** {', '.join(cleaned)}")
        lines.append("")

    # Architecture Diagram
    diagram = bp.get("architecture_diagram") or ""
    if diagram:
        lines.append("## Architecture Diagram")
        lines.append("")
        lines.append("```mermaid")
        lines.append(diagram.strip())
        lines.append("```")
        lines.append("")

    # Commands
    run_commands = _get(bp, "technology", "run_commands", default={}) or {}
    if run_commands:
        lines.append("## Commands")
        lines.append("")
        lines.append("```bash")
        for cmd_name, cmd_value in run_commands.items():
            lines.append(f"# {cmd_name}")
            lines.append(cmd_value)
        lines.append("```")
        lines.append("")

    # Key Rules pointer
    lines.append("## Key Rules")
    lines.append("")
    lines.append("Detailed architecture rules are split into topic files under `.claude/rules/`:")
    lines.append("")
    lines.append("- `architecture.md` — Components, file placement, naming conventions")
    lines.append("- `patterns.md` — Communication patterns, key decisions")
    lines.append("- `guidelines.md` — Implementation guidelines")
    lines.append("- `pitfalls.md` — Common pitfalls, error mapping")
    lines.append("- `dev-rules.md` — Development rules (always/never imperatives)")
    lines.append("- `frontend.md` — Frontend rules (when applicable)")
    lines.append("")

    # Footer
    lines.append("---")
    lines.append("*Auto-generated from structured architecture analysis. Place in project root.*")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# AGENTS.md (mirrors generate_agents_md exactly — 12 sections)
# ---------------------------------------------------------------------------

def generate_agents_md(bp: dict) -> str:
    """Generate AGENTS.md with 12 sections following GitHub's agent file guidelines."""
    timestamp = datetime.now(timezone.utc).isoformat()
    repo = _get(bp, "meta", "repository", default="Unknown Repository") or "Unknown Repository"

    lines = []

    lines.append("# AGENTS.md")
    lines.append("")
    lines.append(f"> Agent guidance for **{repo}**")
    lines.append(f"> Generated: {timestamp}")
    lines.append("")

    # Overview
    summary = _get(bp, "meta", "executive_summary")
    if summary:
        lines.append(summary)
        lines.append("")

    lines.append("---")
    lines.append("")

    # 1. Tech Stack
    stack = _get(bp, "technology", "stack", default=[]) or []
    if stack:
        lines.append("## Tech Stack")
        lines.append("")
        by_cat = defaultdict(list)
        for entry in stack:
            version = f" {entry['version']}" if entry.get("version") else ""
            by_cat[entry.get("category", "Other")].append(f"{entry.get('name', '')}{version}")
        for cat in sorted(by_cat.keys()):
            techs = ", ".join(by_cat[cat])
            lines.append(f"- **{cat}:** {techs}")
        lines.append("")

    # Key Decisions
    ad = _get(bp, "decisions", "architectural_style", default={}) or {}
    key_decs = _get(bp, "decisions", "key_decisions", default=[]) or []
    trade_offs = _get(bp, "decisions", "trade_offs", default=[]) or []
    out_of_scope = _get(bp, "decisions", "out_of_scope", default=[]) or []
    has_decisions = ad.get("chosen") or key_decs or trade_offs or out_of_scope
    if has_decisions:
        lines.append("## Key Decisions")
        lines.append("")
        if ad.get("chosen"):
            lines.append(f"**Architecture:** {ad['chosen']}")
            if ad.get("rationale"):
                lines.append(f"  - *{ad['rationale']}*")
            lines.append("")
        for dec in key_decs:
            lines.append(f"- **{dec.get('title', '')}:** {dec.get('chosen', '')}")
            if dec.get("rationale"):
                lines.append(f"  - *{dec['rationale']}*")
            alternatives = dec.get("alternatives_rejected") or []
            if alternatives:
                lines.append(f"  - Rejected: {', '.join(alternatives)}")
            if dec.get("forced_by"):
                lines.append(f"  - Forced by: {dec['forced_by']}")
            if dec.get("enables"):
                lines.append(f"  - Enables: {dec['enables']}")
        if key_decs:
            lines.append("")
        if trade_offs:
            lines.append("**Trade-offs:**")
            lines.append("")
            lines.append("| Accepted | Benefit |")
            lines.append("|----------|---------|")
            for to in trade_offs:
                accept = to.get("accept", "") or to.get("accepted", "")
                benefit = to.get("benefit", "") or to.get("gained", "")
                lines.append(f"| {accept} | {benefit} |")
            lines.append("")
        if out_of_scope:
            lines.append("**Out of scope:**")
            for item in out_of_scope:
                lines.append(f"- {item}")
            lines.append("")

    # Decision Chain
    decision_chain = _get(bp, "decisions", "decision_chain", default={}) or {}
    if decision_chain.get("root"):
        lines.append("## Decision Chain")
        lines.append("")
        lines.append(f"**Root constraint:** {decision_chain['root']}")
        lines.append("")
        def _render_chain(forces, indent=0):
            for f in (forces or []):
                prefix = "  " * indent + "- "
                lines.append(f"{prefix}**{f.get('decision', '')}**: {f.get('rationale', '')}")
                _render_chain(f.get("forces", []), indent + 1)
        _render_chain(decision_chain.get("forces", []))
        lines.append("")

    # 2. Deployment
    dep = _as_dict(bp.get("deployment"))
    has_deployment = dep.get("runtime_environment") or dep.get("compute_services") or dep.get("ci_cd")
    if has_deployment:
        lines.append("## Deployment")
        lines.append("")
        if dep.get("runtime_environment"):
            lines.append(f"**Runs on:** {dep['runtime_environment']}")
        if dep.get("compute_services"):
            lines.append(f"**Compute:** {', '.join(_as_list(dep['compute_services']))}")
        if dep.get("container_runtime"):
            container = dep["container_runtime"]
            if dep.get("orchestration"):
                container += f" + {dep['orchestration']}"
            lines.append(f"**Container:** {container}")
        if dep.get("ci_cd"):
            lines.append("**CI/CD:**")
            for item in _as_list(dep["ci_cd"]):
                lines.append(f"- {_clean_str_item(item)}")
        if dep.get("distribution"):
            lines.append("**Distribution:**")
            for item in _as_list(dep["distribution"]):
                lines.append(f"- {_clean_str_item(item)}")
        lines.append("")

    # 3. Commands
    run_commands = _get(bp, "technology", "run_commands", default={}) or {}
    if run_commands:
        lines.append("## Commands")
        lines.append("")
        lines.append("```bash")
        for cmd_name, cmd_value in run_commands.items():
            lines.append(f"# {cmd_name}")
            lines.append(cmd_value)
        lines.append("```")
        lines.append("")

    # 4. Project Structure
    project_structure = _get(bp, "technology", "project_structure")
    if project_structure:
        lines.append("## Project Structure")
        lines.append("")
        lines.append("```")
        lines.append(project_structure)
        lines.append("```")
        lines.append("")

    # 5. Code Style
    naming = _get(bp, "architecture_rules", "naming_conventions", default=[]) or []
    templates = _get(bp, "technology", "templates", default=[]) or []
    has_code_style = naming or templates
    if has_code_style:
        lines.append("## Code Style")
        lines.append("")

        if naming:
            for nc in naming:
                examples = ", ".join(f"`{e}`" for e in (nc.get("examples") or [])[:4])
                lines.append(f"- **{nc.get('scope', '')}:** {nc.get('pattern', '')} (e.g. {examples})")
            lines.append("")

        if templates:
            for tmpl in templates[:3]:
                code = tmpl.get("code")
                if code:
                    lines.append(f"### {tmpl.get('component_type', '')}: {tmpl.get('description', '')}")
                    lines.append("")
                    lines.append(f"File: `{tmpl.get('file_path_template', '')}`")
                    lines.append("")
                    lines.append("```")
                    lines.append(code)
                    lines.append("```")
                    lines.append("")

    # 6. Development Rules
    dev_rules = bp.get("development_rules") or []
    if dev_rules:
        by_rule_cat = defaultdict(list)
        for dr in dev_rules:
            cat = (dr.get("category") or "").strip() or "general"
            by_rule_cat[cat].append(dr)

        lines.append("## Development Rules")
        lines.append("")
        for cat_name in sorted(by_rule_cat.keys()):
            heading = cat_name.replace("_", " ").title()
            lines.append(f"### {heading}")
            lines.append("")
            for dr in by_rule_cat[cat_name]:
                if dr.get("source"):
                    lines.append(f"- {dr.get('rule', '')} *(source: `{dr['source']}`)*")
                else:
                    lines.append(f"- {dr.get('rule', '')}")
            lines.append("")

    # 7. Boundaries
    lines.append("## Boundaries")
    lines.append("")
    lines.append("### Always")
    lines.append("")
    always_items = [
        "Run tests before committing",
        "Follow file placement rules (see `.claude/rules/architecture.md`)",
    ]
    for item in always_items:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("### Ask First")
    lines.append("")
    ask_items = [
        "Database schema changes",
        "Adding new dependencies",
        "Modifying CI/CD configuration",
        "Changes to deployment configuration",
    ]
    for item in ask_items:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("### Never")
    lines.append("")
    never_items = [
        "Commit secrets or API keys",
        "Edit vendor/node_modules directories",
        "Remove failing tests without authorization",
    ]
    # Add project-specific nevers from pitfalls
    pitfalls = bp.get("pitfalls") or []
    for pitfall in pitfalls[:3]:
        rec = pitfall.get("recommendation") or ""
        if rec and "never" in rec.lower():
            never_items.append(rec)
    # Add out-of-scope items as nevers
    oos = _get(bp, "decisions", "out_of_scope", default=[]) or []
    for item in oos[:5]:
        never_items.append(item)
    for item in never_items:
        lines.append(f"- {item}")
    lines.append("")

    # 8. Testing
    test_commands = {k: v for k, v in run_commands.items()
                     if any(t in k.lower() for t in ("test", "lint", "check", "verify"))}
    test_stack = [e for e in stack
                  if (e.get("category") or "").lower() in ("testing", "linting")]
    if test_commands or test_stack:
        lines.append("## Testing")
        lines.append("")
        if test_stack:
            for entry in test_stack:
                version = f" {entry['version']}" if entry.get("version") else ""
                lines.append(f"- **{entry.get('name', '')}{version}** — {entry.get('purpose', '')}")
            lines.append("")
        if test_commands:
            lines.append("```bash")
            for cmd_name, cmd_value in test_commands.items():
                lines.append(f"# {cmd_name}")
                lines.append(cmd_value)
            lines.append("```")
            lines.append("")

    # 9. Pitfalls & Gotchas
    if pitfalls:
        lines.append("## Pitfalls & Gotchas")
        lines.append("")
        for pitfall in pitfalls:
            if not pitfall.get("area") and not pitfall.get("description"):
                continue
            area_label = f"**{pitfall['area']}:** " if pitfall.get("area") else ""
            lines.append(f"- {area_label}{pitfall.get('description', '')}")
            stems = pitfall.get("stems_from")
            if stems:
                if isinstance(stems, list):
                    lines.append(f"  - *causal chain: {" → ".join(stems)}*")
                else:
                    lines.append(f"  - *stems from: {stems}*")
            if pitfall.get("recommendation"):
                lines.append(f"  - *{pitfall['recommendation']}*")
        lines.append("")


    # 12. File Placement Quick Reference
    where = _get(bp, "quick_reference", "where_to_put_code", default={}) or {}
    if where:
        lines.append("## File Placement")
        lines.append("")
        for comp_type, loc in where.items():
            lines.append(f"- **{comp_type}** \u2192 `{loc}`")
        lines.append("")

    lines.append("---")
    lines.append("*Auto-generated from structured architecture analysis.*")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

def generate_all(bp: dict) -> dict:
    """Generate all output files from a blueprint dict.

    Returns {path: content} for every output file.
    """
    rule_files = []

    builders = [
        _build_architecture_rule,
        _build_patterns_rule,
        _build_frontend_rule,
        _build_guidelines_rule,
        _build_pitfalls_rule,
        _build_dev_rules_rule,
    ]

    for builder in builders:
        result = builder(bp)
        if result is not None:
            rule_files.append(result)

    files = {
        "CLAUDE.md": generate_claude_md(bp),
        "AGENTS.md": generate_agents_md(bp),
    }

    for rf in rule_files:
        topic = rf["topic"]
        files[f".claude/rules/{topic}.md"] = _render_claude(rf)

    return files


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 renderer.py /path/to/project", file=sys.stderr)
        sys.exit(1)

    project_root = Path(sys.argv[1]).resolve()
    blueprint_path = project_root / ".archie" / "blueprint.json"

    if not blueprint_path.exists():
        print(f"Error: {blueprint_path} not found", file=sys.stderr)
        sys.exit(1)

    bp = json.loads(blueprint_path.read_text())
    files = generate_all(bp)

    # Write all files
    for rel_path, content in files.items():
        full_path = project_root / rel_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content)
        print(f"  Generated {rel_path} ({content.count(chr(10)) + 1} lines)")

    print(f"\nDone: {len(files)} files generated in {project_root}")


if __name__ == "__main__":
    main()
