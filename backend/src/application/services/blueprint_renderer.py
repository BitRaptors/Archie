"""Render a StructuredBlueprint (JSON) into human-readable Markdown."""
from __future__ import annotations

import ast
import base64
import re
import zlib
from collections import defaultdict

from domain.entities.blueprint import StructuredBlueprint


def _clean_str_item(s: str) -> str:
    """Clean a stringified Python dict/list back into readable text.

    AI output sometimes produces list items that are repr'd dicts like
    ``"{'provider': 'GitHub Actions', 'trigger': '...'}"`` instead of
    clean prose.  This function detects that pattern, parses it with
    ``ast.literal_eval``, and flattens the dict into readable text.
    """
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


def _mermaid_live_url(chart: str) -> str:
    """Build a mermaid.live editor URL for the given chart source."""
    payload = '{"code":' + _json_escape(chart) + ',"mermaid":"{\\"theme\\":\\"default\\"}"}'
    compressed = zlib.compress(payload.encode("utf-8"), level=9)
    encoded = base64.urlsafe_b64encode(compressed).decode("ascii")
    return f"https://mermaid.live/edit#pako:{encoded}"


def _json_escape(s: str) -> str:
    """Minimal JSON string escaping (wraps in quotes)."""
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t") + '"'


def _source_links(location: str) -> str:
    """Turn a location string (possibly comma-separated) into clickable source:// links.

    Single path  -> [`path/to/file.swift`](source://path/to/file.swift)
    Multi paths  -> [`file1.swift`](source://file1.swift), [`file2.swift`](source://file2.swift)
    """
    if not location:
        return ""
    parts = [p.strip() for p in location.split(",") if p.strip()]
    return ", ".join(f"[`{p}`](source://{p})" for p in parts)


def _source_link_annotated(entry: str) -> str:
    """Turn an annotated file entry into a source link + annotation text.

    AI often produces entries like:
      "Models/Tag.swift (add enum case)"
      "MainViewController.swift or AppSettingsViewController.swift (add UI)"

    This strips the annotation from the URL and handles "or" alternatives.
    """
    if not entry:
        return ""

    # Extract annotation in parentheses at the end: "path (note)"
    annotation = ""
    match = re.search(r'\s*\(([^)]+)\)\s*$', entry)
    if match:
        annotation = f" ({match.group(1)})"
        entry = entry[:match.start()]

    # Handle "or" alternatives: "fileA.swift or fileB.swift"
    if " or " in entry:
        parts = [p.strip() for p in entry.split(" or ") if p.strip()]
        links = " or ".join(f"[`{p}`](source://{p})" for p in parts)
        return links + annotation

    entry = entry.strip()
    return f"[`{entry}`](source://{entry}){annotation}"


def render_blueprint_markdown(bp: StructuredBlueprint) -> str:
    """Convert a StructuredBlueprint to a comprehensive Markdown document.

    This is a deterministic, template-based renderer — no AI calls.
    The output is meant for human engineers to read.
    """
    lines: list[str] = []

    repo = bp.meta.repository or "Unknown Repository"

    # ── Title ─────────────────────────────────────────────────────────
    lines.append(f"# {repo} — Archie Blueprint")
    lines.append("")
    lines.append(f"> **Analyzed:** {bp.meta.analyzed_at}")
    lines.append(f"> **Schema version:** {bp.meta.schema_version}")
    if bp.meta.platforms:
        lines.append(f"> **Platforms:** {', '.join(bp.meta.platforms)}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ── 1. Architecture Overview (NEW) ────────────────────────────────
    lines.append("## 1. Architecture Overview")
    lines.append("")

    if bp.meta.executive_summary:
        lines.append(bp.meta.executive_summary)
        lines.append("")

    style = bp.meta.architecture_style or "Not determined"
    lines.append(f"**Architecture style:** {style}")
    lines.append("")

    if bp.meta.platforms:
        lines.append(f"**Platforms:** {', '.join(bp.meta.platforms)}")
        lines.append("")

    conf = bp.meta.confidence
    confidence_parts = []
    for field in ("architecture_rules", "decisions", "components", "communication", "technology", "frontend"):
        val = getattr(conf, field, 0.0)
        if val > 0:
            confidence_parts.append(f"{field}: {val:.0%}")
    if confidence_parts:
        lines.append(f"**Confidence:** {' | '.join(confidence_parts)}")
        lines.append("")

    # ── 2. Deployment & Runtime Environment ─────────────────────────────
    dep = bp.deployment
    has_deployment = dep.runtime_environment or dep.compute_services or dep.ci_cd or dep.distribution
    if has_deployment:
        lines.append("## 2. Deployment & Runtime Environment")
        lines.append("")
        if dep.runtime_environment:
            lines.append(f"**Runs on:** {dep.runtime_environment}")
            lines.append("")
        if dep.compute_services:
            if len(dep.compute_services) == 1:
                lines.append(f"**Compute:** {dep.compute_services[0]}")
            else:
                lines.append("**Compute:**")
                for svc in dep.compute_services:
                    lines.append(f"- {svc}")
            lines.append("")
        if dep.container_runtime:
            lines.append(f"**Container:** {dep.container_runtime}")
            if dep.orchestration:
                lines.append(f"**Orchestration:** {dep.orchestration}")
            lines.append("")
        if dep.serverless_functions:
            lines.append(f"**Serverless:** {dep.serverless_functions}")
            lines.append("")
        if dep.ci_cd:
            cleaned = [_clean_str_item(x) for x in dep.ci_cd]
            if len(cleaned) == 1:
                lines.append(f"**CI/CD:** {cleaned[0]}")
            else:
                lines.append("**CI/CD:**")
                for item in cleaned:
                    lines.append(f"- {item}")
            lines.append("")
        if dep.distribution:
            cleaned = [_clean_str_item(x) for x in dep.distribution]
            if len(cleaned) == 1:
                lines.append(f"**Distribution:** {cleaned[0]}")
            else:
                lines.append("**Distribution:**")
                for item in cleaned:
                    lines.append(f"- {item}")
            lines.append("")
        if dep.infrastructure_as_code:
            lines.append(f"**IaC:** {dep.infrastructure_as_code}")
            lines.append("")
        if dep.supporting_services:
            cleaned = [_clean_str_item(x) for x in dep.supporting_services]
            lines.append(f"**Supporting services:** {', '.join(cleaned)}")
            lines.append("")
        if dep.environment_config:
            lines.append(f"**Environment config:** {dep.environment_config}")
            lines.append("")
        if dep.key_files:
            lines.append("**Key deployment files:**")
            for kf in dep.key_files:
                lines.append(f"- [`{kf}`](source://{kf})")
            lines.append("")

    # ── 3. Architecture Diagram ───────────────────────────────────────
    if bp.architecture_diagram:
        lines.append("## 3. Architecture Diagram")
        lines.append("")
        lines.append("```mermaid")
        lines.append(bp.architecture_diagram)
        lines.append("```")
        lines.append("")
        lines.append(f"> [Open diagram in browser]({_mermaid_live_url(bp.architecture_diagram)})")
        lines.append("")

    # ── 3. Project Structure (MOVED from Technology) ──────────────────
    if bp.technology.project_structure:
        lines.append("## 4. Project Structure")
        lines.append("")
        lines.append("```")
        lines.append(bp.technology.project_structure)
        lines.append("```")
        lines.append("")

    # ── 4. Components & Layers ────────────────────────────────────────
    has_components = bp.components.components or bp.components.contracts
    if has_components:
        lines.append("## 5. Components & Layers")
        lines.append("")
        if bp.components.structure_type:
            lines.append(f"**Structure type:** {bp.components.structure_type}")
            lines.append("")

        for comp in bp.components.components:
            platform_tag = f" [{comp.platform}]" if comp.platform else ""
            lines.append(f"### {comp.name}{platform_tag}")
            lines.append("")
            lines.append(f"**Location:** {_source_links(comp.location)}")
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
                    f_path = kf.get('file', '')
                    lines.append(f"- [`{f_path}`](source://{f_path}) — {kf.get('description', '')}")
                lines.append("")

        # Contracts — skip entries with empty interface_name AND empty description
        non_empty_contracts = [
            c for c in bp.components.contracts
            if c.interface_name or c.description
        ]
        if non_empty_contracts:
            lines.append("### Contracts / Interfaces")
            lines.append("")
            for c in non_empty_contracts:
                heading = c.interface_name or "Unnamed Contract"
                lines.append(f"#### {heading}")
                lines.append("")
                if c.description:
                    lines.append(c.description)
                    lines.append("")
                if c.methods:
                    lines.append("Methods: " + ", ".join(f"`{m}`" for m in c.methods))
                    lines.append("")
                if c.implementing_files:
                    lines.append("Implemented in: " + ", ".join(f"[`{f}`](source://{f})" for f in c.implementing_files))
                    lines.append("")

    # ── 5. Architecture Rules ─────────────────────────────────────────
    has_rules = (
        bp.architecture_rules.file_placement_rules
        or bp.architecture_rules.naming_conventions
    )
    if has_rules:
        lines.append("## 6. Architecture Rules")
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

    # ── 6. Development Rules ──────────────────────────────────────────
    if bp.development_rules:
        lines.append("## 7. Development Rules")
        lines.append("")

        dr_by_cat: dict[str, list] = defaultdict(list)
        for dr in bp.development_rules:
            cat = dr.category.strip().replace("_", " ").title() if dr.category else "General"
            dr_by_cat[cat].append(dr)

        for cat_name in sorted(dr_by_cat.keys()):
            lines.append(f"### {cat_name}")
            lines.append("")
            for dr in dr_by_cat[cat_name]:
                if dr.source:
                    lines.append(f"- {dr.rule} *(source: `{dr.source}`)*")
                else:
                    lines.append(f"- {dr.rule}")
            lines.append("")

    # ── 7. Key Decisions & Trade-offs ─────────────────────────────────
    has_decisions = (
        bp.decisions.architectural_style.chosen
        or bp.decisions.key_decisions
        or bp.decisions.trade_offs
        or bp.decisions.out_of_scope
    )
    if has_decisions:
        lines.append("## 8. Key Decisions & Trade-offs")
        lines.append("")

        ad = bp.decisions.architectural_style
        if ad.chosen:
            lines.append(f"### {ad.title or 'Architecture Style'}")
            lines.append("")
            lines.append(f"**Chosen:** {ad.chosen}")
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

    # ── 7. Communication Patterns ─────────────────────────────────────
    has_communication = (
        bp.communication.patterns
        or bp.communication.integrations
        or bp.communication.pattern_selection_guide
    )
    if has_communication:
        lines.append("## 9. Communication Patterns")
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

    # ── 9. Implementation Guidelines ─────────────────────────────────
    if bp.implementation_guidelines:
        lines.append("## 10. Implementation Guidelines")
        lines.append("")

        # Group by category
        by_category: dict[str, list] = defaultdict(list)
        for gl in bp.implementation_guidelines:
            cat = gl.category.strip().title() if gl.category else "General"
            by_category[cat].append(gl)

        for cat_name in sorted(by_category.keys()):
            lines.append(f"### {cat_name}")
            lines.append("")
            for gl in by_category[cat_name]:
                lines.append(f"#### {gl.capability}")
                lines.append("")
                if gl.libraries:
                    lines.append(f"**Libraries:** {', '.join(f'`{lib}`' for lib in gl.libraries)}")
                    lines.append("")
                if gl.pattern_description:
                    lines.append(f"**Pattern:** {gl.pattern_description}")
                    lines.append("")
                if gl.key_files:
                    lines.append("**Key files:**")
                    lines.append("")
                    for kf in gl.key_files:
                        lines.append(f"- [`{kf}`](source://{kf})")
                    lines.append("")
                if gl.usage_example:
                    lines.append("**Example:**")
                    lines.append("")
                    # Strip any existing code fences from AI-generated examples
                    example = gl.usage_example.strip()
                    # Extract prose before the code fence (if any)
                    fence_idx = example.find("```")
                    if fence_idx > 0:
                        prose = example[:fence_idx].strip()
                        if prose:
                            lines.append(prose)
                            lines.append("")
                        example = example[fence_idx:]
                    # Strip outer code fences — we add our own
                    if example.startswith("```"):
                        first_nl = example.find("\n")
                        if first_nl != -1:
                            example = example[first_nl + 1:]
                        else:
                            example = ""
                    if example.rstrip().endswith("```"):
                        example = example.rstrip()[:-3].rstrip()
                    lines.append("```")
                    lines.append(example)
                    lines.append("```")
                    lines.append("")
                if gl.tips:
                    lines.append("**Tips:**")
                    lines.append("")
                    for tip in gl.tips:
                        lines.append(f"- {tip}")
                    lines.append("")

    # ── 10. Developer Recipes ─────────────────────────────────────────
    if bp.developer_recipes:
        lines.append("## 11. Developer Recipes")
        lines.append("")
        for recipe in bp.developer_recipes:
            if not recipe.task:
                continue
            lines.append(f"### {recipe.task}")
            lines.append("")
            if recipe.files:
                lines.append("**Files to touch:**")
                for i, f in enumerate(recipe.files, 1):
                    lines.append(f"{i}. {_source_link_annotated(f)}")
                lines.append("")
            if recipe.steps:
                lines.append("**Steps:**")
                for i, step in enumerate(recipe.steps, 1):
                    # Strip leading number prefixes the AI may have included (e.g. "1. ", "2) ")
                    step = re.sub(r'^\d+[\.\)]\s*', '', step)
                    lines.append(f"{i}. {step}")
                lines.append("")

    # ── 11. Technology Stack ─────────────────────────────────────────
    has_tech = bp.technology.stack or bp.technology.run_commands or bp.technology.templates
    if has_tech:
        lines.append("## 12. Technology Stack")
        lines.append("")

        if bp.technology.stack:
            lines.append("| Category | Technology | Version | Purpose |")
            lines.append("|----------|-----------|---------|---------|")
            for entry in bp.technology.stack:
                lines.append(f"| {entry.category} | {entry.name} | {entry.version} | {entry.purpose} |")
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
                lines.append(f"File: [`{tmpl.file_path_template}`](source://{tmpl.file_path_template})")
                lines.append("")
                lines.append("```")
                lines.append(tmpl.code)
                lines.append("```")
                lines.append("")

    # ── 12. Pitfalls & Edge Cases ─────────────────────────────────────
    if bp.pitfalls:
        lines.append("## 13. Pitfalls & Edge Cases")
        lines.append("")
        for pitfall in bp.pitfalls:
            if not pitfall.area and not pitfall.description:
                continue
            area_label = f"**{pitfall.area}:** " if pitfall.area else ""
            lines.append(f"- {area_label}{pitfall.description}")
            if pitfall.recommendation:
                lines.append(f"  - *Recommendation:* {pitfall.recommendation}")
        lines.append("")

    # ── 13. Quick Reference ─────────────────────────────────────────
    has_quick_ref = (
        bp.quick_reference.where_to_put_code
        or bp.quick_reference.pattern_selection
        or bp.quick_reference.error_mapping
    )
    if has_quick_ref:
        lines.append("## 14. Quick Reference")
        lines.append("")

        if bp.quick_reference.where_to_put_code:
            lines.append("### Where to Put Code")
            lines.append("")
            lines.append("| Component | Location |")
            lines.append("|-----------|----------|")
            for comp_type, loc in bp.quick_reference.where_to_put_code.items():
                lines.append(f"| {comp_type} | `{loc}` |")
            lines.append("")

        if bp.quick_reference.pattern_selection:
            lines.append("### Pattern Selection")
            lines.append("")
            lines.append("| Scenario | Recommended Pattern |")
            lines.append("|----------|---------------------|")
            for scenario, pattern in bp.quick_reference.pattern_selection.items():
                lines.append(f"| {scenario} | {pattern} |")
            lines.append("")

        if bp.quick_reference.error_mapping:
            lines.append("### Error Mapping")
            lines.append("")
            lines.append("| Error | Status Code | Description |")
            lines.append("|-------|------------|-------------|")
            for em in bp.quick_reference.error_mapping:
                lines.append(f"| `{em.error}` | {em.status_code} | {em.description} |")
            lines.append("")

    # ── 14. Frontend Architecture ───────────────────────────────────
    fe = bp.frontend
    has_frontend = fe.framework or fe.ui_components or fe.routing or fe.data_fetching

    if has_frontend:
        lines.append("## 15. Frontend Architecture")
        lines.append("")
        if fe.framework:
            lines.append(f"**Framework:** {fe.framework}")
            lines.append("")
        if fe.rendering_strategy:
            lines.append(f"**Rendering strategy:** {fe.rendering_strategy}")
            lines.append("")
        if fe.styling:
            lines.append(f"**Styling:** {fe.styling}")
            lines.append("")

        # State management
        sm = fe.state_management
        if sm.approach:
            lines.append("### State Management")
            lines.append("")
            lines.append(f"**Approach:** {sm.approach}")
            lines.append("")
            if sm.server_state:
                lines.append(f"- **Server state:** {sm.server_state}")
            if sm.local_state:
                lines.append(f"- **Local state:** {sm.local_state}")
            if sm.rationale:
                lines.append(f"- **Rationale:** {sm.rationale}")
            lines.append("")
            if sm.global_state:
                lines.append("**Global stores:**")
                lines.append("")
                for gs in sm.global_state:
                    store = gs.get("store", gs.get("name", ""))
                    purpose = gs.get("purpose", "")
                    lines.append(f"- `{store}` — {purpose}")
                lines.append("")

        # UI Components
        if fe.ui_components:
            lines.append("### UI Components")
            lines.append("")
            lines.append("| Name | Type | Location | Description |")
            lines.append("|------|------|----------|-------------|")
            for uc in fe.ui_components:
                lines.append(
                    f"| {uc.name} | {uc.component_type} | {_source_links(uc.location)} | {uc.description} |"
                )
            lines.append("")

        # Routing
        if fe.routing:
            # Build name→location lookup from UI components so we can link class names
            comp_location: dict[str, str] = {}
            for uc in fe.ui_components:
                if uc.name and uc.location:
                    comp_location[uc.name] = uc.location

            lines.append("### Routing")
            lines.append("")
            lines.append("| Path | Component | Auth | Description |")
            lines.append("|------|-----------|------|-------------|")
            for r in fe.routing:
                auth = "Yes" if r.auth_required else "No"
                loc = comp_location.get(r.component, "")
                comp_cell = _source_links(loc) if loc else f"`{r.component}`"
                lines.append(f"| `{r.path}` | {comp_cell} | {auth} | {r.description} |")
            lines.append("")

        # Data Fetching
        if fe.data_fetching:
            lines.append("### Data Fetching Patterns")
            lines.append("")
            for df in fe.data_fetching:
                lines.append(f"#### {df.name}")
                lines.append("")
                lines.append(f"**Mechanism:** {df.mechanism}")
                lines.append("")
                if df.when_to_use:
                    lines.append(f"**When to use:** {df.when_to_use}")
                    lines.append("")
                if df.examples:
                    lines.append("**Examples:** " + ", ".join(f"`{e}`" for e in df.examples))
                    lines.append("")

        # Key Conventions
        if fe.key_conventions:
            lines.append("### Frontend Conventions")
            lines.append("")
            for conv in fe.key_conventions:
                lines.append(f"- {conv}")
            lines.append("")

    # ── Footer ────────────────────────────────────────────────────────
    lines.append("---")
    lines.append("")
    lines.append("*This document was auto-generated from structured analysis data.*")
    lines.append("")

    return "\n".join(lines)
