"""Intent Layer renderer — deterministic rendering of folder data to markdown."""
from __future__ import annotations

from domain.entities.intent_layer import (
    FolderNode,
    FolderBlueprint,
    FolderEnrichment,
    CodeExample,
)

MAX_LINES = 200


class IntentLayerRenderer:
    """Renders folder data into CLAUDE.md markdown files."""

    # ── Blueprint-driven rendering (deterministic) ──

    def render_from_blueprint(
        self,
        folder: FolderNode,
        fb: FolderBlueprint,
        repo_name: str,
    ) -> str:
        """Render a CLAUDE.md from FolderBlueprint data. Hard cap: 200 lines."""
        sections = [
            self._render_header(folder, fb, repo_name),
            self._render_navigation(folder, fb),
            self._render_what_goes_here(fb),
            self._render_key_files(fb),
            self._render_common_tasks(fb),
            self._render_gotchas(fb),
            self._render_dependencies(fb),
            self._render_naming_conventions(fb),
            self._render_contracts_interfaces(fb),
            self._render_how_things_work(fb),
            self._render_communication(fb),
            self._render_templates(fb),
            self._render_subfolders(fb),
        ]

        lines_used = 0
        output_sections: list[str] = []
        for section in sections:
            if not section:
                continue
            section_lines = section.count("\n") + 1
            # Account for the "\n\n" separator between sections
            separator_lines = 2 if output_sections else 0
            if lines_used + separator_lines + section_lines > MAX_LINES - 4:
                output_sections.append("> Full details in [CODEBASE_MAP.md](../CODEBASE_MAP.md)")
                break
            output_sections.append(section)
            lines_used += separator_lines + section_lines

        return "\n\n".join(output_sections) + "\n"

    def render_minimal(
        self,
        folder: FolderNode,
        fb: FolderBlueprint,
        repo_name: str,
    ) -> str:
        """Render a minimal CLAUDE.md for folders with no blueprint coverage."""
        lines: list[str] = []

        folder_label = f"{folder.name}/" if folder.path else repo_name
        lines.append(f"# {folder_label}")
        lines.append("")

        # Navigation
        nav = self._render_navigation(folder, fb)
        if nav:
            lines.append(nav)
            lines.append("")

        # File listing
        if folder.files:
            lines.append("## Files")
            for f in folder.files[:20]:
                lines.append(f"- `{f}`")
            if len(folder.files) > 20:
                lines.append(f"- ... and {len(folder.files) - 20} more")
            lines.append("")

        # Extensions
        if folder.extensions:
            lines.append(f"**Extensions:** {', '.join(f'`.{e}`' for e in folder.extensions)}")
            lines.append("")

        return "\n".join(lines).rstrip() + "\n"

    def render_passthrough(
        self,
        folder: FolderNode,
        fb: FolderBlueprint,
        repo_name: str,
    ) -> str:
        """One-liner for namespace-only pass-through folders."""
        folder_label = f"{folder.name}/" if folder.path else repo_name
        child_name = folder.children[0].rsplit("/", 1)[-1] if folder.children else "child"
        return f"# {folder_label}\n> Namespace folder — see [`{child_name}/`]({child_name}/CLAUDE.md) for documentation.\n"

    # ── Section renderers ──

    def _render_header(
        self,
        folder: FolderNode,
        fb: FolderBlueprint,
        repo_name: str,
    ) -> str:
        folder_label = f"{folder.name}/" if folder.path else repo_name
        lines = [f"# {folder_label}"]
        if fb.component_responsibility:
            lines.append(f"> {fb.component_responsibility}")
        return "\n".join(lines)

    def _render_navigation(
        self,
        folder: FolderNode,
        fb: FolderBlueprint,
    ) -> str:
        lines = ["## Navigation", ""]
        has_content = False

        if fb.parent_path or (folder.path and not fb.parent_path):
            if folder.path:
                lines.append("**Parent:** [`{}/`](../CLAUDE.md)".format(
                    fb.parent_path.rsplit("/", 1)[-1] if fb.parent_path else "root"
                ))
                has_content = True

        if fb.peer_paths:
            peer_links = []
            for pp in fb.peer_paths:
                peer_name = pp.rsplit("/", 1)[-1]
                # Compute relative path from current folder to peer
                peer_links.append(f"[`{peer_name}/`](../{peer_name}/CLAUDE.md)")
            lines.append("**Peers:** " + " | ".join(peer_links))
            has_content = True

        if fb.children_summaries:
            child_links = []
            for cs in fb.children_summaries:
                child_name = cs["path"].rsplit("/", 1)[-1]
                child_links.append(f"[`{child_name}/`]({child_name}/CLAUDE.md)")
            lines.append("**Children:** " + " | ".join(child_links))
            has_content = True

        if not has_content:
            return ""

        return "\n".join(lines)

    def _render_what_goes_here(self, fb: FolderBlueprint) -> str | None:
        if not fb.file_placement_rules and not fb.where_to_put:
            return None
        lines = ["## What Goes Here", ""]
        if fb.file_placement_rules:
            for rule in fb.file_placement_rules:
                desc = rule.get("description") or rule.get("component_type", "")
                pattern = rule.get("naming_pattern", "")
                if desc:
                    line = f"- **{desc}**"
                    if pattern:
                        line += f" — `{pattern}`"
                    lines.append(line)
        if fb.where_to_put:
            for code_type, location in fb.where_to_put.items():
                lines.append(f"- {code_type} → `{location}`")
        return "\n".join(lines)

    def _render_key_files(self, fb: FolderBlueprint) -> str | None:
        if not fb.key_files:
            return None
        lines = ["## Key Files", ""]
        lines.append("| File | Description |")
        lines.append("|------|-------------|")
        for kf in fb.key_files:
            file_name = kf.get("file", kf.get("name", ""))
            desc = kf.get("description", kf.get("purpose", ""))
            lines.append(f"| `{file_name}` | {desc} |")
        return "\n".join(lines)

    def _render_common_tasks(self, fb: FolderBlueprint) -> str | None:
        if not fb.recipes:
            return None
        lines = ["## Common Tasks", ""]
        for recipe in fb.recipes:
            lines.append(f"### {recipe['task']}")
            if recipe.get("files"):
                lines.append(f"**Files:** {', '.join(f'`{f}`' for f in recipe['files'])}")
            if recipe.get("steps"):
                for i, step in enumerate(recipe["steps"], 1):
                    lines.append(f"{i}. {step}")
            lines.append("")
        return "\n".join(lines).rstrip()

    def _render_gotchas(self, fb: FolderBlueprint) -> str | None:
        if not fb.pitfalls:
            return None
        lines = ["## Gotchas", ""]
        for pitfall in fb.pitfalls:
            lines.append(f"- **{pitfall['area']}**: {pitfall['description']}")
            if pitfall.get("recommendation"):
                lines.append(f"  - *Recommendation:* {pitfall['recommendation']}")
        return "\n".join(lines)

    def _render_dependencies(self, fb: FolderBlueprint) -> str | None:
        if not fb.depends_on and not fb.exposes_to:
            return None
        lines = ["## Dependencies", ""]
        if fb.depends_on:
            lines.append("**Depends on:** " + ", ".join(f"`{d}`" for d in fb.depends_on))
        if fb.exposes_to:
            lines.append("**Exposes to:** " + ", ".join(f"`{e}`" for e in fb.exposes_to))
        return "\n".join(lines)

    def _render_naming_conventions(self, fb: FolderBlueprint) -> str | None:
        if not fb.naming_conventions:
            return None
        lines = ["## Naming Conventions", ""]
        for nc in fb.naming_conventions:
            scope = nc.get("scope", "")
            pattern = nc.get("pattern", "")
            lines.append(f"- **{scope}**: `{pattern}`")
        return "\n".join(lines)

    def _render_contracts_interfaces(self, fb: FolderBlueprint) -> str | None:
        if not fb.contracts and not fb.key_interfaces:
            return None
        lines = ["## Contracts & Interfaces", ""]
        for contract in fb.contracts:
            lines.append(f"### {contract.get('interface_name', '')}")
            if contract.get("description"):
                lines.append(contract["description"])
            if contract.get("methods"):
                for m in contract["methods"]:
                    lines.append(f"- `{m}`")
            lines.append("")
        for iface in fb.key_interfaces:
            lines.append(f"### {iface.get('name', '')}")
            if iface.get("description"):
                lines.append(iface["description"])
            if iface.get("methods"):
                for m in iface["methods"]:
                    lines.append(f"- `{m}`")
            lines.append("")
        return "\n".join(lines).rstrip()

    def _render_how_things_work(self, fb: FolderBlueprint) -> str | None:
        if not fb.implementation_guidelines:
            return None
        lines = ["## How Things Work", ""]
        for ig in fb.implementation_guidelines:
            lines.append(f"### {ig['capability']}")
            if ig.get("libraries"):
                lines.append(f"**Libraries:** {', '.join(ig['libraries'])}")
            if ig.get("pattern_description"):
                lines.append(ig["pattern_description"])
            lines.append("")
        return "\n".join(lines).rstrip()

    def _render_communication(self, fb: FolderBlueprint) -> str | None:
        if not fb.communication_patterns:
            return None
        lines = ["## Communication", ""]
        for cp in fb.communication_patterns:
            lines.append(f"- **{cp['name']}**: {cp.get('when_to_use', '')}")
        return "\n".join(lines)

    def _render_templates(self, fb: FolderBlueprint) -> str | None:
        if not fb.templates:
            return None
        lines = ["## Templates", ""]
        for tmpl in fb.templates:
            lines.append(f"### {tmpl.get('component_type', 'Template')}")
            if tmpl.get("file_path_template"):
                lines.append(f"**Path:** `{tmpl['file_path_template']}`")
            if tmpl.get("code"):
                lines.append("```")
                lines.append(tmpl["code"])
                lines.append("```")
            lines.append("")
        return "\n".join(lines).rstrip()

    def _render_subfolders(self, fb: FolderBlueprint) -> str | None:
        if not fb.children_summaries:
            return None
        lines = ["## Subfolders", ""]
        for cs in fb.children_summaries:
            child_name = cs["path"].rsplit("/", 1)[-1]
            resp = cs.get("responsibility", "")
            lines.append(f"- [`{child_name}/`]({child_name}/CLAUDE.md) — {resp}")
        return "\n".join(lines)

    # ── Hybrid rendering (AI enrichment + deterministic base) ──

    def render_hybrid(
        self,
        folder: FolderNode,
        fb: FolderBlueprint,
        enrichment: FolderEnrichment,
        repo_name: str,
    ) -> str:
        """Render a CLAUDE.md from combined AI enrichment and blueprint data.

        Section priority: highest-value compound learning first,
        deterministic structural data last. Hard cap: 200 lines.
        """
        # High-value AI sections first, deterministic last
        sections = [
            self._render_hybrid_header(folder, fb, enrichment, repo_name),
            self._render_patterns(enrichment),
            self._render_navigation(folder, fb),
            self._render_hybrid_key_files(fb, enrichment),
            self._render_key_imports(enrichment),
            self._render_hybrid_common_task(fb, enrichment),
            self._render_code_examples(enrichment),
            self._render_hybrid_anti_patterns(enrichment),
            self._render_testing(enrichment),
            self._render_debugging(enrichment),
            self._render_decisions(enrichment),
            self._render_what_goes_here(fb),
            self._render_dependencies(fb),
            self._render_templates(fb),
            self._render_subfolders(fb),
        ]

        lines_used = 0
        output_sections: list[str] = []
        for section in sections:
            if not section:
                continue
            section_lines = section.count("\n") + 1
            separator_lines = 2 if output_sections else 0
            if lines_used + separator_lines + section_lines > MAX_LINES - 4:
                output_sections.append("> Full details in [CODEBASE_MAP.md](../CODEBASE_MAP.md)")
                break
            output_sections.append(section)
            lines_used += separator_lines + section_lines

        return "\n\n".join(output_sections) + "\n"

    def _render_hybrid_header(
        self,
        folder: FolderNode,
        fb: FolderBlueprint,
        enrichment: FolderEnrichment,
        repo_name: str,
    ) -> str:
        folder_label = f"{folder.name}/" if folder.path else repo_name
        lines = [f"# {folder_label}"]
        # AI purpose takes priority, fall back to blueprint
        purpose = enrichment.purpose if enrichment.has_ai_content and enrichment.purpose else fb.component_responsibility
        if purpose:
            lines.append(f"> {purpose}")
        return "\n".join(lines)

    @staticmethod
    def _render_patterns(enrichment: FolderEnrichment) -> str | None:
        if not enrichment.patterns:
            return None
        lines = ["## Patterns", ""]
        for p in enrichment.patterns:
            lines.append(f"- {p}")
        return "\n".join(lines)

    def _render_hybrid_key_files(
        self,
        fb: FolderBlueprint,
        enrichment: FolderEnrichment,
    ) -> str | None:
        # AI key file guides take priority (3-column table with modification guide)
        if enrichment.has_ai_content and enrichment.key_file_guides:
            lines = ["## Key Files", ""]
            lines.append("| File | What It Does | How to Modify |")
            lines.append("|------|-------------|---------------|")
            for kfg in enrichment.key_file_guides:
                lines.append(f"| `{kfg.file}` | {kfg.purpose} | {kfg.modification_guide} |")
            return "\n".join(lines)
        # Fall back to blueprint key files (2-column table)
        return self._render_key_files(fb)

    def _render_hybrid_common_task(
        self,
        fb: FolderBlueprint,
        enrichment: FolderEnrichment,
    ) -> str | None:
        # AI common task takes priority
        if enrichment.has_ai_content and enrichment.common_task:
            ct = enrichment.common_task
            lines = [f"## {ct.task}", ""]
            for i, step in enumerate(ct.steps, 1):
                lines.append(f"{i}. {step}")
            return "\n".join(lines)
        # Fall back to blueprint recipes
        return self._render_common_tasks(fb)

    @staticmethod
    def _render_hybrid_anti_patterns(enrichment: FolderEnrichment) -> str | None:
        if not enrichment.anti_patterns:
            return None
        lines = ["## Don't", ""]
        for ap in enrichment.anti_patterns:
            lines.append(f"- {ap}")
        return "\n".join(lines)

    @staticmethod
    def _render_testing(enrichment: FolderEnrichment) -> str | None:
        if not enrichment.testing:
            return None
        lines = ["## Testing", ""]
        for t in enrichment.testing:
            lines.append(f"- {t}")
        return "\n".join(lines)

    @staticmethod
    def _render_debugging(enrichment: FolderEnrichment) -> str | None:
        if not enrichment.debugging:
            return None
        lines = ["## Debugging", ""]
        for d in enrichment.debugging:
            lines.append(f"- {d}")
        return "\n".join(lines)

    @staticmethod
    def _render_code_examples(enrichment: FolderEnrichment) -> str | None:
        if not enrichment.code_examples:
            return None
        lines = ["## Usage Examples", ""]
        for ex in enrichment.code_examples:
            lines.append(f"### {ex.label}")
            lang = ex.language or ""
            lines.append(f"```{lang}")
            lines.append(ex.code)
            lines.append("```")
            lines.append("")
        return "\n".join(lines).rstrip()

    @staticmethod
    def _render_key_imports(enrichment: FolderEnrichment) -> str | None:
        if not enrichment.key_imports:
            return None
        lines = ["## Key Imports", ""]
        for imp in enrichment.key_imports:
            lines.append(f"- `{imp}`")
        return "\n".join(lines)

    @staticmethod
    def _render_decisions(enrichment: FolderEnrichment) -> str | None:
        if not enrichment.decisions:
            return None
        lines = ["## Why It's Built This Way", ""]
        for d in enrichment.decisions:
            lines.append(f"- {d}")
        return "\n".join(lines)

