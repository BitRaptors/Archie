"""Tool implementations for querying and validating architecture.

All tools read from the structured blueprint JSON — the single source of truth
produced by the analysis pipeline. No markdown or static reference files are used.
"""
import fnmatch
import json
import re
from pathlib import Path
from typing import Optional

from domain.entities.blueprint import StructuredBlueprint


def _glob_match(path: str, pattern: str) -> bool:
    """Check if a file path matches a glob pattern.

    Supports patterns like ``src/api/**``, ``**/*.py``, and plain prefixes.
    """
    # Normalise separators
    path = path.replace("\\", "/")
    pattern = pattern.replace("\\", "/")

    # If no ** in pattern, use fnmatch for single-level matching
    if "**" not in pattern:
        # fnmatch treats * as matching everything including /, so we match by segments
        pat_parts = pattern.split("/")
        path_parts = path.split("/")
        if len(pat_parts) != len(path_parts):
            return False
        return all(fnmatch.fnmatch(p, pp) for p, pp in zip(path_parts, pat_parts))

    # For ** patterns, use recursive segment matching
    pat_parts = pattern.split("/")
    path_parts = path.split("/")
    return _match_segments(path_parts, pat_parts)


def _match_segments(path_parts: list[str], pat_parts: list[str]) -> bool:
    """Recursively match path segments against pattern segments."""
    if not pat_parts and not path_parts:
        return True
    if not pat_parts:
        return False
    if pat_parts[0] == "**":
        rest = pat_parts[1:]
        # ** can match zero or more segments
        for i in range(len(path_parts) + 1):
            if _match_segments(path_parts[i:], rest):
                return True
        return False
    if not path_parts:
        return False
    if fnmatch.fnmatch(path_parts[0], pat_parts[0]):
        return _match_segments(path_parts[1:], pat_parts[1:])
    return False


def _slice_markdown(content: str) -> dict[str, str]:
    """Slice markdown content by ## headers.

    Returns:
        Dict mapping slugs to content sections.
    """
    sections: dict[str, str] = {}

    parts = re.split(r'^(##\s+.*)$', content, flags=re.MULTILINE)

    if parts:
        intro = parts[0].strip()
        if intro:
            sections["introduction"] = intro

    for i in range(1, len(parts), 2):
        header_line = parts[i]
        header_text = header_line.replace('##', '').strip()
        slug = _slugify(header_text)
        section_content = parts[i + 1].strip() if i + 1 < len(parts) else ""
        sections[slug] = f"{header_line}\n\n{section_content}"

    return sections


def _slugify(text: str) -> str:
    """Convert text to a URL-friendly slug."""
    text = re.sub(r'^\d+(\.\d+)*\s*', '', text)
    slug = re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')
    return slug


class BlueprintTools:
    """Manages blueprint query and validation tools.

    All data comes from the structured JSON blueprint (``StructuredBlueprint``)
    stored per-repository. No static reference files are used.
    """

    def __init__(self, storage_dir: Path):
        self.storage_dir = storage_dir

    # ── Blueprint loading ─────────────────────────────────────────────

    def _load_structured_blueprint(self, repo_id: str) -> StructuredBlueprint | None:
        """Load the structured JSON blueprint for a repository."""
        json_file = self.storage_dir / "blueprints" / repo_id / "blueprint.json"
        if not json_file.exists():
            return None
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
            return StructuredBlueprint.model_validate(data)
        except Exception:
            return None

    def _resolve_repo_display_name(self, repo_id: str) -> str:
        """Resolve a human-readable name for a repository from blueprint.json."""
        bp = self._load_structured_blueprint(repo_id)
        if bp and bp.meta.repository:
            return bp.meta.repository
        return repo_id

    # ── Repository listing ────────────────────────────────────────────

    def list_analyzed_repositories(self) -> str:
        """List all successfully analyzed repositories with their IDs and names."""
        blueprints_dir = self.storage_dir / "blueprints"
        if not blueprints_dir.exists():
            return "No analyzed repositories found."

        entries: list[tuple[str, str]] = []
        for d in sorted(blueprints_dir.iterdir()):
            if not d.is_dir():
                continue
            if not (d / "blueprint.json").exists():
                continue
            rid = d.name
            display = self._resolve_repo_display_name(rid)
            entries.append((rid, display))

        if not entries:
            return "No successfully analyzed repositories found."

        response = "# Analyzed Repositories\n\n"
        response += "Use the `repo_id` value when calling other tools.\n\n"
        response += "| repo_id | Repository |\n"
        response += "|---------|------------|\n"
        for rid, display in entries:
            response += f"| `{rid}` | **{display}** |\n"

        return response

    # ── Blueprint reading tools ───────────────────────────────────────

    def get_repository_blueprint(self, repo_id: str) -> str:
        """Get the full blueprint for a repository (rendered from JSON)."""
        bp = self._load_structured_blueprint(repo_id)
        if not bp:
            return f"Blueprint for repository '{repo_id}' not found."
        from application.services.blueprint_renderer import render_blueprint_markdown
        return render_blueprint_markdown(bp)

    def list_repository_sections(self, repo_id: str) -> str:
        """List all available sections in a repository's blueprint."""
        bp = self._load_structured_blueprint(repo_id)
        if not bp:
            return f"Blueprint for repository '{repo_id}' not found."
        from application.services.blueprint_renderer import render_blueprint_markdown
        content = render_blueprint_markdown(bp)
        sections = _slice_markdown(content)
        display = self._resolve_repo_display_name(repo_id)

        response = f"# Blueprint Sections for {display}\n\n"
        for section_id in sections:
            response += f"- `{section_id}`\n"
        return response

    def get_repository_section(self, repo_id: str, section_id: str) -> str:
        """Get a specific section from a repository's blueprint."""
        bp = self._load_structured_blueprint(repo_id)
        if not bp:
            return f"Blueprint for repository '{repo_id}' not found."
        from application.services.blueprint_renderer import render_blueprint_markdown
        content = render_blueprint_markdown(bp)
        sections = _slice_markdown(content)

        section_content = sections.get(section_id)
        if not section_content:
            return (
                f"Section '{section_id}' not found in blueprint for '{repo_id}'. "
                f"Available sections: {', '.join(sections.keys())}"
            )
        return section_content

    # ── Architecture guardrail tools ──────────────────────────────────

    def validate_import(self, repo_id: str, source_file: str, target_import: str) -> str:
        """Check whether an import is allowed by the architecture rules.

        Args:
            repo_id: Repository ID
            source_file: File that contains the import (e.g. "src/api/routes/users.py")
            target_import: Module being imported (e.g. "src/infrastructure/db")

        Returns:
            Human-readable validation result with machine-parseable JSON.
        """
        bp = self._load_structured_blueprint(repo_id)
        if not bp:
            return f"No structured blueprint found for repository '{repo_id}'. Run analysis first."

        violations: list[dict] = []
        allowed_by: list[str] = []

        for dc in bp.architecture_rules.dependency_constraints:
            if not dc.source_pattern:
                continue

            if not _glob_match(source_file, dc.source_pattern):
                continue

            # Check forbidden
            for forbidden in dc.forbidden_imports:
                if _glob_match(target_import, forbidden):
                    violations.append({
                        "rule": dc.source_description or dc.source_pattern,
                        "forbidden_pattern": forbidden,
                        "severity": dc.severity,
                        "rationale": dc.rationale,
                    })

            # Check allowed
            for allowed in dc.allowed_imports:
                if _glob_match(target_import, allowed):
                    allowed_by.append(dc.source_description or dc.source_pattern)

        result = {
            "source_file": source_file,
            "target_import": target_import,
            "is_valid": len(violations) == 0,
            "violations": violations,
            "allowed_by": allowed_by,
        }

        if violations:
            lines = [f"**VIOLATION** — Import `{target_import}` from `{source_file}` is NOT allowed.\n"]
            for v in violations:
                lines.append(f"- Rule: {v['rule']}")
                lines.append(f"  Forbidden: `{v['forbidden_pattern']}` (severity: {v['severity']})")
                if v["rationale"]:
                    lines.append(f"  Reason: {v['rationale']}")
            lines.append(f"\n```json\n{json.dumps(result, indent=2)}\n```")
            return "\n".join(lines)

        if allowed_by:
            return (
                f"**ALLOWED** — Import `{target_import}` from `{source_file}` is permitted.\n"
                f"Allowed by: {', '.join(allowed_by)}\n"
                f"\n```json\n{json.dumps(result, indent=2)}\n```"
            )

        return (
            f"**UNGUARDED** — No dependency constraint covers `{source_file}` → `{target_import}`.\n"
            f"This import is not covered by any architecture rule. "
            f"Verify manually that it does not violate the intended layer boundaries.\n"
            f"\n```json\n{json.dumps(result, indent=2)}\n```"
        )

    def where_to_put(self, repo_id: str, component_type: str) -> str:
        """Find the correct location for a new component.

        Args:
            repo_id: Repository ID
            component_type: Type of component (e.g. "service", "controller", "entity")

        Returns:
            Location guidance with naming pattern and examples.
        """
        bp = self._load_structured_blueprint(repo_id)
        if not bp:
            return f"No structured blueprint found for repository '{repo_id}'. Run analysis first."

        type_lower = component_type.lower().strip()
        matches: list[dict] = []

        # Search file placement rules
        for fp in bp.architecture_rules.file_placement_rules:
            if type_lower in fp.component_type.lower():
                matches.append({
                    "source": "file_placement_rule",
                    "component_type": fp.component_type,
                    "location": fp.location,
                    "naming_pattern": fp.naming_pattern,
                    "example": fp.example,
                    "description": fp.description,
                })

        # Search quick_reference.where_to_put_code
        for key, loc in bp.quick_reference.where_to_put_code.items():
            if type_lower in key.lower():
                matches.append({
                    "source": "quick_reference",
                    "component_type": key,
                    "location": loc,
                })

        if not matches:
            available = set()
            for fp in bp.architecture_rules.file_placement_rules:
                available.add(fp.component_type)
            for key in bp.quick_reference.where_to_put_code:
                available.add(key)
            return (
                f"No placement rule found for '{component_type}'.\n"
                f"Available component types: {', '.join(sorted(available))}"
            )

        lines = [f"# Where to put: {component_type}\n"]
        for m in matches:
            lines.append(f"**Location:** `{m['location']}`")
            if m.get("naming_pattern"):
                lines.append(f"**Naming pattern:** `{m['naming_pattern']}`")
            if m.get("example"):
                lines.append(f"**Example:** `{m['example']}`")
            if m.get("description"):
                lines.append(f"**Description:** {m['description']}")
            lines.append("")

        lines.append(f"```json\n{json.dumps(matches, indent=2)}\n```")
        return "\n".join(lines)

    def check_naming(self, repo_id: str, scope: str, name: str) -> str:
        """Check if a name follows the project's naming conventions.

        Args:
            repo_id: Repository ID
            scope: Scope of the name (e.g. "classes", "functions", "files")
            name: The name to check (e.g. "UserService", "get_user")

        Returns:
            Validation result with matching conventions.
        """
        bp = self._load_structured_blueprint(repo_id)
        if not bp:
            return f"No structured blueprint found for repository '{repo_id}'. Run analysis first."

        scope_lower = scope.lower().strip()
        matches: list[dict] = []
        violations: list[dict] = []

        for nc in bp.architecture_rules.naming_conventions:
            if scope_lower not in nc.scope.lower():
                continue

            try:
                if nc.pattern.startswith("^") or nc.pattern.endswith("$"):
                    if re.match(nc.pattern, name):
                        matches.append({
                            "scope": nc.scope,
                            "pattern": nc.pattern,
                            "description": nc.description,
                            "examples": nc.examples,
                        })
                    else:
                        violations.append({
                            "scope": nc.scope,
                            "pattern": nc.pattern,
                            "description": nc.description,
                            "examples": nc.examples,
                        })
                else:
                    # Non-regex pattern — report as informational convention
                    matches.append({
                        "scope": nc.scope,
                        "pattern": nc.pattern,
                        "description": nc.description,
                        "examples": nc.examples,
                        "note": "Convention pattern is not a regex; verify manually.",
                    })
            except re.error:
                matches.append({
                    "scope": nc.scope,
                    "pattern": nc.pattern,
                    "description": nc.description,
                    "examples": nc.examples,
                    "note": "Pattern could not be parsed as regex.",
                })

        result = {
            "name": name,
            "scope": scope,
            "is_valid": len(violations) == 0,
            "matching_conventions": matches,
            "violations": violations,
        }

        if violations:
            lines = [f"**NAMING ISSUE** — `{name}` does not match convention for {scope}.\n"]
            for v in violations:
                lines.append(f"- Expected: {v['pattern']} ({v['description']})")
                if v["examples"]:
                    lines.append(f"  Examples: {', '.join(f'`{e}`' for e in v['examples'][:3])}")
            lines.append(f"\n```json\n{json.dumps(result, indent=2)}\n```")
            return "\n".join(lines)

        if matches:
            lines = [f"**OK** — `{name}` follows naming convention for {scope}.\n"]
            for m in matches:
                lines.append(f"- Convention: {m['pattern']} ({m['description']})")
            lines.append(f"\n```json\n{json.dumps(result, indent=2)}\n```")
            return "\n".join(lines)

        return (
            f"No naming convention found for scope '{scope}'.\n"
            f"Available scopes: {', '.join(set(nc.scope for nc in bp.architecture_rules.naming_conventions))}"
        )
