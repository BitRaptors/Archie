"""Render a StructuredBlueprint (JSON) into human-readable Markdown."""
from __future__ import annotations

from domain.entities.blueprint import StructuredBlueprint


def render_blueprint_markdown(bp: StructuredBlueprint) -> str:
    """Convert a StructuredBlueprint to a comprehensive Markdown document.

    This is a deterministic, template-based renderer — no AI calls.
    The output is meant for human engineers to read.
    """
    lines: list[str] = []

    repo = bp.meta.repository or "Unknown Repository"
    style = bp.meta.architecture_style or "Not determined"

    # ── Title & Purpose ───────────────────────────────────────────────
    lines.append(f"# {repo} — Architecture Blueprint")
    lines.append("")
    lines.append(f"> **Architecture style:** {style}")
    lines.append(f"> **Analyzed:** {bp.meta.analyzed_at}")
    lines.append(f"> **Schema version:** {bp.meta.schema_version}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ── 1. Decisions ──────────────────────────────────────────────────
    lines.append("## 1. Architectural Decisions")
    lines.append("")

    ad = bp.decisions.architectural_style
    if ad.chosen:
        lines.append(f"### Why {ad.chosen}?")
        lines.append("")
        lines.append(ad.rationale or "*No rationale provided.*")
        lines.append("")
        if ad.alternatives_rejected:
            lines.append("**Alternatives considered and rejected:** " + ", ".join(ad.alternatives_rejected))
            lines.append("")

    for dec in bp.decisions.key_decisions:
        lines.append(f"### {dec.title}")
        lines.append("")
        lines.append(f"**Chosen:** {dec.chosen}")
        lines.append("")
        lines.append(dec.rationale or "")
        lines.append("")

    if bp.decisions.trade_offs:
        lines.append("### Trade-offs Accepted")
        lines.append("")
        lines.append("| We Accept | In Exchange For |")
        lines.append("|-----------|----------------|")
        for t in bp.decisions.trade_offs:
            lines.append(f"| {t.accept} | {t.benefit} |")
        lines.append("")

    if bp.decisions.out_of_scope:
        lines.append("### Out of Scope")
        lines.append("")
        for item in bp.decisions.out_of_scope:
            lines.append(f"- {item}")
        lines.append("")

    # ── 2. Architecture Rules ─────────────────────────────────────────
    lines.append("## 2. Architecture Rules")
    lines.append("")

    # Dependency constraints
    if bp.architecture_rules.dependency_constraints:
        lines.append("### Dependency Constraints")
        lines.append("")
        for dc in bp.architecture_rules.dependency_constraints:
            sev_icon = {"error": "🚫", "warning": "⚠️", "info": "ℹ️"}.get(dc.severity, "•")
            lines.append(f"#### {sev_icon} {dc.source_description or dc.source_pattern}")
            lines.append("")
            lines.append(f"**Source:** `{dc.source_pattern}`")
            lines.append("")
            if dc.allowed_imports:
                lines.append("**Allowed imports:**")
                for ai in dc.allowed_imports:
                    lines.append(f"- ✅ `{ai}`")
            if dc.forbidden_imports:
                lines.append("**Forbidden imports:**")
                for fi in dc.forbidden_imports:
                    lines.append(f"- ❌ `{fi}`")
            if dc.rationale:
                lines.append("")
                lines.append(f"*{dc.rationale}*")
            lines.append("")

    # File placement
    if bp.architecture_rules.file_placement_rules:
        lines.append("### File Placement Rules")
        lines.append("")
        lines.append("| Component Type | Location | Naming Pattern | Example |")
        lines.append("|---------------|----------|----------------|---------|")
        for fp in bp.architecture_rules.file_placement_rules:
            lines.append(
                f"| {fp.component_type} | `{fp.location}` | `{fp.naming_pattern}` | `{fp.example}` |"
            )
        lines.append("")

    # Naming conventions
    if bp.architecture_rules.naming_conventions:
        lines.append("### Naming Conventions")
        lines.append("")
        lines.append("| Scope | Pattern | Examples |")
        lines.append("|-------|---------|----------|")
        for nc in bp.architecture_rules.naming_conventions:
            examples = ", ".join(f"`{e}`" for e in nc.examples[:3])
            lines.append(f"| {nc.scope} | {nc.pattern} | {examples} |")
        lines.append("")

    # ── 3. Components ─────────────────────────────────────────────────
    lines.append("## 3. Components")
    lines.append("")
    if bp.components.structure_type:
        lines.append(f"**Structure type:** {bp.components.structure_type}")
        lines.append("")

    for comp in bp.components.components:
        lines.append(f"### {comp.name}")
        lines.append("")
        lines.append(f"**Location:** `{comp.location}`")
        lines.append("")
        lines.append(f"**Responsibility:** {comp.responsibility}")
        lines.append("")
        if comp.depends_on:
            lines.append(f"**Depends on:** {', '.join(comp.depends_on)}")
            lines.append("")
        if comp.exposes_to:
            lines.append(f"**Exposes to:** {', '.join(comp.exposes_to)}")
            lines.append("")
        if comp.key_interfaces:
            lines.append("**Key interfaces:**")
            for ki in comp.key_interfaces:
                methods = ", ".join(f"`{m}`" for m in ki.methods[:5])
                lines.append(f"- `{ki.name}` — {ki.description or methods}")
            lines.append("")
        if comp.key_files:
            lines.append("**Key files:**")
            for kf in comp.key_files:
                lines.append(f"- `{kf.get('file', '')}` — {kf.get('description', '')}")
            lines.append("")

    # Contracts
    if bp.components.contracts:
        lines.append("### Contracts / Interfaces")
        lines.append("")
        for c in bp.components.contracts:
            lines.append(f"#### {c.interface_name}")
            lines.append("")
            if c.description:
                lines.append(c.description)
                lines.append("")
            if c.methods:
                lines.append("Methods: " + ", ".join(f"`{m}`" for m in c.methods))
                lines.append("")
            if c.implementing_files:
                lines.append("Implemented in: " + ", ".join(f"`{f}`" for f in c.implementing_files))
                lines.append("")

    # ── 4. Communication ──────────────────────────────────────────────
    lines.append("## 4. Communication Patterns")
    lines.append("")

    for pat in bp.communication.patterns:
        lines.append(f"### {pat.name}")
        lines.append("")
        lines.append(f"**When to use:** {pat.when_to_use}")
        lines.append("")
        lines.append(f"**How it works:** {pat.how_it_works}")
        lines.append("")
        if pat.examples:
            lines.append("**Examples:**")
            for ex in pat.examples:
                lines.append(f"- {ex}")
            lines.append("")

    if bp.communication.integrations:
        lines.append("### Third-Party Integrations")
        lines.append("")
        lines.append("| Service | Purpose | Integration Point |")
        lines.append("|---------|---------|------------------|")
        for integ in bp.communication.integrations:
            lines.append(f"| {integ.service} | {integ.purpose} | `{integ.integration_point}` |")
        lines.append("")

    if bp.communication.pattern_selection_guide:
        lines.append("### Pattern Selection Guide")
        lines.append("")
        lines.append("| Scenario | Pattern | Rationale |")
        lines.append("|----------|---------|-----------|")
        for psg in bp.communication.pattern_selection_guide:
            lines.append(f"| {psg.scenario} | {psg.pattern} | {psg.rationale} |")
        lines.append("")

    # ── 5. Quick Reference ────────────────────────────────────────────
    lines.append("## 5. Quick Reference")
    lines.append("")

    if bp.quick_reference.where_to_put_code:
        lines.append("### Where to Put Code")
        lines.append("")
        lines.append("| Component | Location |")
        lines.append("|-----------|----------|")
        for comp_type, loc in bp.quick_reference.where_to_put_code.items():
            lines.append(f"| {comp_type} | `{loc}` |")
        lines.append("")

    if bp.quick_reference.error_mapping:
        lines.append("### Error Mapping")
        lines.append("")
        lines.append("| Error | Status Code | Description |")
        lines.append("|-------|------------|-------------|")
        for em in bp.quick_reference.error_mapping:
            lines.append(f"| `{em.error}` | {em.status_code} | {em.description} |")
        lines.append("")

    # ── 6. Technology ─────────────────────────────────────────────────
    lines.append("## 6. Technology Stack")
    lines.append("")

    if bp.technology.stack:
        lines.append("| Category | Technology | Version | Purpose |")
        lines.append("|----------|-----------|---------|---------|")
        for entry in bp.technology.stack:
            lines.append(f"| {entry.category} | {entry.name} | {entry.version} | {entry.purpose} |")
        lines.append("")

    if bp.technology.project_structure:
        lines.append("### Project Structure")
        lines.append("")
        lines.append("```")
        lines.append(bp.technology.project_structure)
        lines.append("```")
        lines.append("")

    if bp.technology.run_commands:
        lines.append("### Running the Application")
        lines.append("")
        lines.append("```bash")
        for label, cmd in bp.technology.run_commands.items():
            lines.append(f"# {label}")
            lines.append(cmd)
            lines.append("")
        lines.append("```")
        lines.append("")

    # Code templates
    if bp.technology.templates:
        lines.append("### Code Templates")
        lines.append("")
        for tmpl in bp.technology.templates:
            lines.append(f"#### {tmpl.component_type}: {tmpl.description}")
            lines.append("")
            lines.append(f"File: `{tmpl.file_path_template}`")
            lines.append("")
            lines.append("```")
            lines.append(tmpl.code)
            lines.append("```")
            lines.append("")

    # ── Footer ────────────────────────────────────────────────────────
    lines.append("---")
    lines.append("")
    lines.append("*This document was auto-generated from structured analysis data.*")
    lines.append("")

    return "\n".join(lines)
