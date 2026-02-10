"""Resource handlers for blueprint documents.

All repository-specific data is loaded from blueprint.json (the single
source of truth).  Human-readable markdown is rendered on-the-fly via
``blueprint_renderer.render_blueprint_markdown``.
"""
import json as _json
from pathlib import Path
from typing import Dict, Optional

from mcp.types import Resource

from domain.entities.blueprint import StructuredBlueprint
from .utils.markdown import find_markdown_files, get_doc_by_id, read_markdown_file, slice_markdown


def _load_blueprint(repo_dir: Path) -> Optional[StructuredBlueprint]:
    """Load and validate blueprint.json from a repository directory."""
    json_file = repo_dir / "blueprint.json"
    if not json_file.exists():
        return None
    try:
        data = _json.loads(json_file.read_text(encoding="utf-8"))
        return StructuredBlueprint.model_validate(data)
    except Exception:
        return None


def _render_markdown(bp: StructuredBlueprint) -> str:
    """Render a structured blueprint to Markdown."""
    from application.services.blueprint_renderer import render_blueprint_markdown
    return render_blueprint_markdown(bp)


class BlueprintResources:
    """Manages blueprint document resources."""

    def __init__(self, docs_dir: Path, storage_dir: Optional[Path] = None, repository_repository=None):
        self.docs_dir = docs_dir
        self.storage_dir = storage_dir or docs_dir.parent / "backend" / "storage"
        self._repository_repository = repository_repository
        self._repo_cache: Dict[str, str] = {}
        self._repo_repo_initialized = False

    # ------------------------------------------------------------------
    # Display name resolution
    # ------------------------------------------------------------------

    async def _ensure_repo_repository(self):
        """Lazily initialize repository repository if database is available."""
        if self._repo_repo_initialized:
            return

        if self._repository_repository is None:
            try:
                from infrastructure.persistence.supabase_client import get_supabase_client_async
                from infrastructure.persistence.supabase_adapter import SupabaseAdapter
                from infrastructure.persistence.repository_repository import RepositoryRepository

                supabase_client = await get_supabase_client_async()
                db = SupabaseAdapter(supabase_client)
                self._repository_repository = RepositoryRepository(db=db)
            except Exception:
                pass

        self._repo_repo_initialized = True

    async def _get_repo_display_name(self, repo_id: str) -> str:
        """Get display name for repository (owner/name) or fall back to UUID."""
        if repo_id in self._repo_cache:
            return self._repo_cache[repo_id]

        # Try DB first
        await self._ensure_repo_repository()
        if self._repository_repository:
            try:
                repo = await self._repository_repository.get_by_id(repo_id)
                if repo:
                    display_name = f"{repo.owner}/{repo.name}"
                    self._repo_cache[repo_id] = display_name
                    return display_name
            except Exception:
                pass

        # Try blueprint.json meta.repository
        bp_dir = self.storage_dir / "blueprints" / repo_id
        bp = _load_blueprint(bp_dir)
        if bp and bp.meta.repository:
            self._repo_cache[repo_id] = bp.meta.repository
            return bp.meta.repository

        return repo_id

    # ------------------------------------------------------------------
    # Resource listing
    # ------------------------------------------------------------------

    async def list_resources(self) -> list[Resource]:
        """List all available blueprint resources."""
        resources = []

        blueprints_dir = self.storage_dir / "blueprints"
        if not blueprints_dir.exists():
            return resources

        for repo_dir in blueprints_dir.iterdir():
            if not repo_dir.is_dir():
                continue

            bp = _load_blueprint(repo_dir)
            if bp is None:
                continue

            repo_id = repo_dir.name
            display_name = await self._get_repo_display_name(repo_id)

            # Full blueprint resource
            resources.append(Resource(
                uri=f"blueprint://analyzed/{repo_id}",
                name=f"Repository Blueprint: {display_name}",
                description=f"Generated backend architecture for {display_name}",
                mimeType="text/markdown",
            ))

            # Granular sections (rendered on the fly)
            try:
                markdown = _render_markdown(bp)
                sections = slice_markdown(markdown)
                for section_id in sections:
                    if section_id == "introduction":
                        continue
                    section_title = section_id.replace("-", " ").title()
                    resources.append(Resource(
                        uri=f"blueprint://analyzed/{repo_id}/{section_id}",
                        name=f"{display_name} - {section_title}",
                        description=f"Granular section '{section_id}' for {display_name}",
                        mimeType="text/markdown",
                    ))
            except Exception:
                continue

        return resources

    # ------------------------------------------------------------------
    # Resource reading
    # ------------------------------------------------------------------

    def get_resource(self, uri: str) -> Optional[tuple[str, str]]:
        """Get resource content by URI.

        Returns:
            Tuple of (mime_type, content) or None if not found
        """
        if uri == "blueprint://analyzed":
            return self._get_analyzed_repositories()
        elif uri.startswith("blueprint://analyzed/"):
            path_parts = uri.replace("blueprint://analyzed/", "").split("/")
            repo_id = path_parts[0]

            if len(path_parts) == 1:
                return self._get_repository_blueprint(repo_id)
            else:
                section_id = path_parts[1]
                return self._get_repository_section(repo_id, section_id)

        return None

    # ------------------------------------------------------------------
    # Internal helpers — all derive from blueprint.json
    # ------------------------------------------------------------------

    def _get_analyzed_repositories(self) -> tuple[str, str]:
        """Get list of analyzed repositories."""
        blueprints_dir = self.storage_dir / "blueprints"
        if not blueprints_dir.exists():
            return "text/markdown", "# Analyzed Repositories\n\nNo analyzed repositories found."

        entries: list[tuple[str, str]] = []
        for d in sorted(blueprints_dir.iterdir()):
            if not d.is_dir():
                continue
            bp = _load_blueprint(d)
            if bp is None:
                continue
            rid = d.name
            display = bp.meta.repository or rid
            entries.append((rid, display))

        markdown = "# Analyzed Repositories\n\n"
        if not entries:
            markdown += "No successfully analyzed repositories found."
        else:
            for rid, display in entries:
                markdown += f"- **{display}** — `blueprint://analyzed/{rid}`\n"

        return "text/markdown", markdown

    def _get_repository_blueprint(self, repo_id: str) -> tuple[str, str]:
        """Get full repository blueprint (rendered from JSON)."""
        bp_dir = self.storage_dir / "blueprints" / repo_id
        bp = _load_blueprint(bp_dir)
        if bp is None:
            return "text/markdown", f"# Blueprint for {repo_id}\n\nBlueprint not found."
        return "text/markdown", _render_markdown(bp)

    def _get_repository_section(self, repo_id: str, section_id: str) -> tuple[str, str]:
        """Get specific section of a repository blueprint."""
        bp_dir = self.storage_dir / "blueprints" / repo_id
        bp = _load_blueprint(bp_dir)
        if bp is None:
            return "text/markdown", f"# Section {section_id} for {repo_id}\n\nBlueprint not found."

        markdown = _render_markdown(bp)
        sections = slice_markdown(markdown)
        section_content = sections.get(section_id)
        if not section_content:
            return "text/markdown", (
                f"# Section {section_id} for {repo_id}\n\n"
                f"Section not found. Available: {', '.join(sections.keys())}"
            )
        return "text/markdown", section_content

    # ------------------------------------------------------------------
    # Reference-doc helpers (unchanged — these read static DOCS/)
    # ------------------------------------------------------------------

    def _get_full_blueprint(self, stack: str) -> tuple[str, str]:
        """Get full blueprint content for a stack."""
        stack_dir = self.docs_dir / stack
        if not stack_dir.exists():
            return "text/markdown", f"# {stack.title()} Architecture Blueprint\n\nNot found."

        index_file = stack_dir / "_index.md"
        if index_file.exists():
            _, content = read_markdown_file(index_file)
            return "text/markdown", content

        return "text/markdown", f"# {stack.title()} Architecture Blueprint\n\nIndex file not found."

    def _get_patterns_index(self) -> tuple[str, str]:
        """Get index of all patterns."""
        patterns = []

        for stack_name in ("backend", "frontend"):
            patterns_dir = self.docs_dir / stack_name / "patterns"
            if not patterns_dir.exists():
                continue
            for md_file in patterns_dir.glob("*.md"):
                if md_file.name == "_index.md":
                    continue
                try:
                    frontmatter, content = read_markdown_file(md_file)
                    patterns.append({
                        "id": frontmatter.get("id", md_file.stem),
                        "title": frontmatter.get("title", md_file.stem),
                        "category": stack_name,
                        "tags": frontmatter.get("tags", []),
                    })
                except Exception:
                    continue

        markdown = "# Architectural Patterns\n\n"
        for cat in ("backend", "frontend"):
            markdown += f"## {cat.title()} Patterns\n\n"
            for p in [x for x in patterns if x["category"] == cat]:
                markdown += f"- **{p['title']}** (`{p['id']}`)\n"
                if p.get("tags"):
                    markdown += f"  Tags: {', '.join(p['tags'])}\n"
            markdown += "\n"

        return "text/markdown", markdown

    def _get_doc_by_id(self, doc_id: str) -> Optional[tuple[str, str]]:
        """Get document content by ID."""
        result = get_doc_by_id(self.docs_dir, doc_id)
        if result:
            _, _, content = result
            return "text/markdown", content
        return None
