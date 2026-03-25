"""CodebaseMapRenderer — generates flat CODEBASE_MAP.md from a StructuredBlueprint."""
from __future__ import annotations

from datetime import datetime, timezone

from domain.entities.blueprint import StructuredBlueprint


class CodebaseMapRenderer:
    """Generates a comprehensive CODEBASE_MAP.md from a StructuredBlueprint.

    Entirely deterministic: same blueprint → same output.
    """

    def render(self, blueprint: StructuredBlueprint) -> str:
        """Render the full CODEBASE_MAP.md."""
        sections = [
            self._render_header(blueprint),
            self._render_architecture_diagram(blueprint),
            self._render_directory_structure(blueprint),
            self._render_module_guide(blueprint),
            self._render_common_tasks(blueprint),
            self._render_gotchas(blueprint),
            self._render_technology_stack(blueprint),
            self._render_run_commands(blueprint),
        ]
        return "\n\n".join(s for s in sections if s) + "\n"

    # ── Sections ──

    def _render_header(self, bp: StructuredBlueprint) -> str:
        lines = [f"# {bp.meta.repository or 'Codebase'} — Architecture Map"]

        if bp.meta.executive_summary:
            lines.append("")
            lines.append(f"> {bp.meta.executive_summary}")

        meta_parts = []
        if bp.meta.architecture_style:
            meta_parts.append(f"**Architecture:** {bp.meta.architecture_style}")
        if bp.meta.platforms:
            meta_parts.append(f"**Platforms:** {', '.join(bp.meta.platforms)}")
        meta_parts.append(f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d')}")

        if meta_parts:
            lines.append("")
            lines.append(" | ".join(meta_parts))

        return "\n".join(lines)

    def _render_architecture_diagram(self, bp: StructuredBlueprint) -> str | None:
        if not bp.architecture_diagram:
            return None
        lines = [
            "## Architecture Diagram",
            "",
            "```mermaid",
            bp.architecture_diagram,
            "```",
        ]
        return "\n".join(lines)

    def _render_directory_structure(self, bp: StructuredBlueprint) -> str | None:
        if bp.technology.project_structure:
            lines = [
                "## Directory Structure",
                "",
                "```",
                bp.technology.project_structure,
                "```",
            ]
            return "\n".join(lines)

        # Generate from components
        components = bp.components.components
        if not components:
            return None
        lines = ["## Directory Structure", ""]
        lines.append("```")
        for comp in sorted(components, key=lambda c: c.location):
            if comp.location:
                lines.append(f"{comp.location}/  # {comp.responsibility[:60]}" if comp.responsibility else f"{comp.location}/")
        lines.append("```")
        return "\n".join(lines)

    def _render_module_guide(self, bp: StructuredBlueprint) -> str | None:
        components = bp.components.components
        if not components:
            return None
        lines = ["## Module Guide", ""]
        for comp in components:
            lines.append(f"### {comp.name}")
            if comp.location:
                lines.append(f"**Location:** `{comp.location}`")
            if comp.responsibility:
                lines.append(f"\n{comp.responsibility}")
            if comp.key_files:
                lines.append("")
                lines.append("| File | Description |")
                lines.append("|------|-------------|")
                for kf in comp.key_files:
                    lines.append(f"| `{kf.get('file', kf.get('name', ''))}` | {kf.get('description', kf.get('purpose', ''))} |")
            if comp.depends_on:
                lines.append(f"\n**Depends on:** {', '.join(comp.depends_on)}")
            if comp.key_interfaces:
                lines.append("")
                for ki in comp.key_interfaces:
                    lines.append(f"- **{ki.name}**: {ki.description}")
            lines.append("")
        return "\n".join(lines).rstrip()

    def _render_common_tasks(self, bp: StructuredBlueprint) -> str | None:
        if not bp.developer_recipes:
            return None
        lines = ["## Common Tasks", ""]
        for recipe in bp.developer_recipes:
            lines.append(f"### {recipe.task}")
            if recipe.files:
                lines.append(f"**Files:** {', '.join(f'`{f}`' for f in recipe.files)}")
            if recipe.steps:
                lines.append("")
                for i, step in enumerate(recipe.steps, 1):
                    lines.append(f"{i}. {step}")
            lines.append("")
        return "\n".join(lines).rstrip()

    def _render_gotchas(self, bp: StructuredBlueprint) -> str | None:
        if not bp.pitfalls:
            return None
        lines = ["## Gotchas", ""]
        for pitfall in bp.pitfalls:
            lines.append(f"### {pitfall.area}")
            lines.append(pitfall.description)
            if pitfall.recommendation:
                lines.append(f"\n*Recommendation:* {pitfall.recommendation}")
            lines.append("")
        return "\n".join(lines).rstrip()

    def _render_technology_stack(self, bp: StructuredBlueprint) -> str | None:
        if not bp.technology.stack:
            return None
        lines = ["## Technology Stack", ""]
        lines.append("| Category | Name | Version | Purpose |")
        lines.append("|----------|------|---------|---------|")
        for entry in bp.technology.stack:
            lines.append(f"| {entry.category} | {entry.name} | {entry.version} | {entry.purpose} |")
        return "\n".join(lines)

    def _render_run_commands(self, bp: StructuredBlueprint) -> str | None:
        if not bp.technology.run_commands:
            return None
        lines = ["## Run Commands", ""]
        lines.append("```bash")
        for cmd_name, cmd in bp.technology.run_commands.items():
            lines.append(f"# {cmd_name}")
            lines.append(cmd)
            lines.append("")
        lines.append("```")
        return "\n".join(lines)
