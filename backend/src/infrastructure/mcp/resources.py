"""Resource handlers for blueprint documents."""

from pathlib import Path
from typing import Any, Dict, Optional

from mcp.types import Resource

from .utils.markdown import find_markdown_files, get_doc_by_id, read_markdown_file, slice_markdown


class BlueprintResources:
    """Manages blueprint document resources."""
    
    def __init__(self, docs_dir: Path, storage_dir: Optional[Path] = None, repository_repository=None):
        self.docs_dir = docs_dir
        self.storage_dir = storage_dir or docs_dir.parent / "backend" / "storage"
        self._repository_repository = repository_repository
        self._repo_cache: Dict[str, str] = {}  # Cache: repo_id -> "owner/name"
        self._repo_repo_initialized = False
    
    async def _ensure_repo_repository(self):
        """Lazily initialize repository repository if database is available."""
        if self._repo_repo_initialized:
            return
        
        if self._repository_repository is None:
            try:
                from infrastructure.persistence.supabase_client import get_supabase_client_async
                from infrastructure.persistence.repository_repository import SupabaseRepositoryRepository
                
                # Use async client
                supabase_client = await get_supabase_client_async()
                self._repository_repository = SupabaseRepositoryRepository(client=supabase_client)
            except Exception:
                # If database connection fails, repository_repository stays None
                # Resources will fall back to using UUIDs
                pass
        
        self._repo_repo_initialized = True
    
    async def _get_repo_display_name(self, repo_id: str) -> str:
        """Get display name for repository (owner/name) or fall back to UUID."""
        if repo_id in self._repo_cache:
            return self._repo_cache[repo_id]
        
        # Ensure repository repository is initialized
        await self._ensure_repo_repository()
        
        # Try to fetch from database if repository_repository is available
        if self._repository_repository:
            try:
                repo = await self._repository_repository.get_by_id(repo_id)
                if repo:
                    display_name = f"{repo.owner}/{repo.name}"
                    self._repo_cache[repo_id] = display_name
                    return display_name
            except Exception:
                # If database lookup fails, fall back to UUID
                pass
        
        # Fall back to UUID
        return repo_id
    
    async def list_resources(self) -> list[Resource]:
        """List all available blueprint resources."""
        resources = []
        
        # Analyzed repositories (dynamically from storage) - this is the main feature
        blueprints_dir = self.storage_dir / "blueprints"
        if blueprints_dir.exists():
            for repo_dir in blueprints_dir.iterdir():
                if repo_dir.is_dir():
                    repo_id = repo_dir.name
                    blueprint_file = repo_dir / "backend_blueprint.md"
                    if blueprint_file.exists():
                        # Get display name (owner/name or UUID)
                        display_name = await self._get_repo_display_name(repo_id)
                        
                        # Full blueprint resource
                        resources.append(Resource(
                            uri=f"blueprint://analyzed/{repo_id}",
                            name=f"Repository Blueprint: {display_name}",
                            description=f"Generated backend architecture for {display_name}",
                            mimeType="text/markdown"
                        ))
                        
                        # Granular sections
                        try:
                            content = blueprint_file.read_text(encoding='utf-8')
                            sections = slice_markdown(content)
                            for section_id in sections.keys():
                                if section_id == "introduction":
                                    continue
                                section_title = section_id.replace('-', ' ').title()
                                resources.append(Resource(
                                    uri=f"blueprint://analyzed/{repo_id}/{section_id}",
                                    name=f"{display_name} - {section_title}",
                                    description=f"Granular section '{section_id}' for {display_name}",
                                    mimeType="text/markdown"
                                ))
                        except Exception:
                            continue
        
        return resources
    
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
                # Full blueprint
                return self._get_repository_blueprint(repo_id)
            else:
                # Specific section
                section_id = path_parts[1]
                return self._get_repository_section(repo_id, section_id)
        
        return None
    
    def _get_analyzed_repositories(self) -> tuple[str, str]:
        """Get list of analyzed repositories."""
        blueprints_dir = self.storage_dir / "blueprints"
        if not blueprints_dir.exists():
            return "text/markdown", "# Analyzed Repositories\n\nNo analyzed repositories found."
            
        repo_ids = [d.name for d in blueprints_dir.iterdir() if d.is_dir() and (d / "backend_blueprint.md").exists()]
        
        markdown = "# Analyzed Repositories\n\n"
        if not repo_ids:
            markdown += "No successfully analyzed repositories found."
        else:
            for rid in repo_ids:
                markdown += f"- **{rid}** (`blueprint://analyzed/{rid}`)\n"
                
        return "text/markdown", markdown
    
    def _get_repository_blueprint(self, repo_id: str) -> tuple[str, str]:
        """Get repository blueprint."""
        blueprint_file = self.storage_dir / "blueprints" / repo_id / "backend_blueprint.md"
        if not blueprint_file.exists():
            return "text/markdown", f"# Blueprint for {repo_id}\n\nBlueprint not found."
            
        return "text/markdown", blueprint_file.read_text(encoding='utf-8')
        
    def _get_repository_section(self, repo_id: str, section_id: str) -> tuple[str, str]:
        """Get specific section of a repository blueprint."""
        blueprint_file = self.storage_dir / "blueprints" / repo_id / "backend_blueprint.md"
        if not blueprint_file.exists():
            return "text/markdown", f"# Section {section_id} for {repo_id}\n\nBlueprint not found."
            
        content = blueprint_file.read_text(encoding='utf-8')
        sections = slice_markdown(content)
        
        section_content = sections.get(section_id)
        if not section_content:
            return "text/markdown", f"# Section {section_id} for {repo_id}\n\nSection not found. Available: {', '.join(sections.keys())}"
            
        return "text/markdown", section_content
    
    def _get_unified_blueprints(self) -> tuple[str, str]:
        """Get list of unified blueprints."""
        # Would fetch from cloud API
        return "text/markdown", "# Unified Blueprints\n\n(List would be fetched from cloud API)"
    
    def _get_unified_blueprint(self, blueprint_id: str) -> tuple[str, str]:
        """Get unified blueprint content."""
        # Would fetch from cloud storage
        return "text/markdown", f"# Unified Blueprint {blueprint_id}\n\n(Would fetch from cloud storage)"
    
    def _get_full_blueprint(self, stack: str) -> tuple[str, str]:
        """Get full blueprint content for a stack."""
        stack_dir = self.docs_dir / stack
        if not stack_dir.exists():
            return "text/markdown", f"# {stack.title()} Architecture Blueprint\n\nNot found."
        
        # Read index file
        index_file = stack_dir / "_index.md"
        if index_file.exists():
            _, content = read_markdown_file(index_file)
            return "text/markdown", content
        
        return "text/markdown", f"# {stack.title()} Architecture Blueprint\n\nIndex file not found."
    
    def _get_patterns_index(self) -> tuple[str, str]:
        """Get index of all patterns."""
        patterns = []
        
        # Backend patterns
        backend_patterns_dir = self.docs_dir / "backend" / "patterns"
        if backend_patterns_dir.exists():
            for md_file in backend_patterns_dir.glob("*.md"):
                if md_file.name == "_index.md":
                    continue
                try:
                    frontmatter, content = read_markdown_file(md_file)
                    patterns.append({
                        "id": frontmatter.get("id", md_file.stem),
                        "title": frontmatter.get("title", md_file.stem),
                        "category": "backend",
                        "tags": frontmatter.get("tags", [])
                    })
                except Exception:
                    continue
        
        # Frontend patterns
        frontend_patterns_dir = self.docs_dir / "frontend" / "patterns"
        if frontend_patterns_dir.exists():
            for md_file in frontend_patterns_dir.glob("*.md"):
                if md_file.name == "_index.md":
                    continue
                try:
                    frontmatter, content = read_markdown_file(md_file)
                    patterns.append({
                        "id": frontmatter.get("id", md_file.stem),
                        "title": frontmatter.get("title", md_file.stem),
                        "category": "frontend",
                        "tags": frontmatter.get("tags", [])
                    })
                except Exception:
                    continue
        
        # Format as markdown
        markdown = "# Architectural Patterns\n\n"
        markdown += "## Backend Patterns\n\n"
        for pattern in [p for p in patterns if p["category"] == "backend"]:
            markdown += f"- **{pattern['title']}** (`{pattern['id']}`)\n"
            if pattern.get("tags"):
                markdown += f"  Tags: {', '.join(pattern['tags'])}\n"
        
        markdown += "\n## Frontend Patterns\n\n"
        for pattern in [p for p in patterns if p["category"] == "frontend"]:
            markdown += f"- **{pattern['title']}** (`{pattern['id']}`)\n"
            if pattern.get("tags"):
                markdown += f"  Tags: {', '.join(pattern['tags'])}\n"
        
        return "text/markdown", markdown
    
    def _get_doc_by_id(self, doc_id: str) -> Optional[tuple[str, str]]:
        """Get document content by ID."""
        result = get_doc_by_id(self.docs_dir, doc_id)
        if result:
            _, _, content = result
            return "text/markdown", content
        return None

