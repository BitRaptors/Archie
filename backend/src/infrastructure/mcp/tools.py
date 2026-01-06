"""Tool implementations for querying and validating architecture."""

from pathlib import Path
from typing import Literal, Optional

from .resources import BlueprintResources
from .utils.markdown import get_doc_by_id, slice_markdown
from .validators import review_component, validate_file_structure, validate_layer_compliance


class BlueprintTools:
    """Manages blueprint query and validation tools."""
    
    def __init__(self, docs_dir: Path, storage_dir: Optional[Path] = None):
        self.docs_dir = docs_dir
        self.storage_dir = storage_dir or docs_dir.parent / "backend" / "storage"
        self.resources = BlueprintResources(docs_dir, storage_dir=self.storage_dir)
    
    def get_pattern(self, pattern_id: str) -> str:
        """Get detailed information about an architectural pattern.
        
        Args:
            pattern_id: Pattern identifier (e.g., "context-hook", "service-registry")
        """
        result = get_doc_by_id(self.docs_dir, pattern_id)
        if result:
            _, frontmatter, content = result
            title = frontmatter.get("title", pattern_id)
            category = frontmatter.get("category", "unknown")
            
            response = f"# {title}\n\n"
            response += f"**Category:** {category}\n\n"
            if frontmatter.get("tags"):
                response += f"**Tags:** {', '.join(frontmatter.get('tags', []))}\n\n"
            response += "---\n\n"
            response += content
            return response
        
        # Try to find by partial match
        from .utils.markdown import find_markdown_files, read_markdown_file
        for md_file in find_markdown_files(self.docs_dir):
            try:
                frontmatter, content = read_markdown_file(md_file)
                if pattern_id.lower() in frontmatter.get("id", "").lower() or \
                   pattern_id.lower() in frontmatter.get("title", "").lower():
                    title = frontmatter.get("title", md_file.stem)
                    response = f"# {title}\n\n"
                    response += content
                    return response
            except Exception:
                continue
        
        return f"Pattern '{pattern_id}' not found. Use list_patterns to see available patterns."
    
    def list_patterns(self, stack: Optional[Literal["backend", "frontend"]] = None) -> str:
        """List all available patterns with summaries.
        
        Args:
            stack: Optional filter by stack (backend or frontend)
        """
        from .utils.markdown import find_markdown_files, read_markdown_file
        
        patterns = []
        for md_file in find_markdown_files(self.docs_dir):
            # Only look in patterns directories
            if "patterns" not in str(md_file):
                continue
            
            if md_file.name == "_index.md":
                continue
            
            try:
                frontmatter, content = read_markdown_file(md_file)
                pattern_category = frontmatter.get("category", "unknown")
                
                if stack and pattern_category != stack:
                    continue
                
                # Extract first paragraph as summary
                summary = ""
                lines = content.split("\n")
                for line in lines:
                    line = line.strip()
                    if line and not line.startswith("#") and not line.startswith("```"):
                        summary = line[:200] + ("..." if len(line) > 200 else "")
                        break
                
                patterns.append({
                    "id": frontmatter.get("id", md_file.stem),
                    "title": frontmatter.get("title", md_file.stem),
                    "category": pattern_category,
                    "summary": summary
                })
            except Exception:
                continue
        
        # Format response
        response = "# Architectural Patterns\n\n"
        if stack:
            response += f"## {stack.title()} Patterns\n\n"
        else:
            response += "## All Patterns\n\n"
        
        for pattern in sorted(patterns, key=lambda p: (p["category"], p["title"])):
            response += f"### {pattern['title']} (`{pattern['id']}`)\n\n"
            response += f"- **Category:** {pattern['category']}\n"
            if pattern['summary']:
                response += f"- **Summary:** {pattern['summary']}\n"
            response += "\n"
        
        return response
    
    def get_layer_rules(self, layer: Literal["presentation", "application", "domain", "infrastructure"]) -> str:
        """Get what a specific layer can/cannot do.
        
        Args:
            layer: Layer name (presentation, application, domain, or infrastructure)
        """
        from .utils.patterns import BACKEND_LAYER_RULES
        
        if layer not in BACKEND_LAYER_RULES:
            return f"Unknown layer: {layer}. Available layers: {', '.join(BACKEND_LAYER_RULES.keys())}"
        
        rules = BACKEND_LAYER_RULES[layer]
        response = f"# {layer.title()} Layer Rules\n\n"
        response += f"{rules.get('description', '')}\n\n"
        
        if "forbidden_imports" in rules:
            response += "## Forbidden Imports\n\n"
            response += "This layer should NOT import:\n\n"
            for imp in rules["forbidden_imports"]:
                response += f"- `{imp}`\n"
            response += "\n"
        
        if "allowed_imports" in rules:
            response += "## Allowed Imports\n\n"
            response += "This layer may import:\n\n"
            for imp in rules["allowed_imports"]:
                response += f"- `{imp}`\n"
            response += "\n"
        
        # Get layer documentation
        layer_doc_id = f"backend-layer-architecture"
        result = get_doc_by_id(self.docs_dir, layer_doc_id)
        if result:
            _, _, content = result
            response += "---\n\n## Full Documentation\n\n"
            response += content
        
        return response
    
    def get_principle(self, principle_name: str) -> str:
        """Get a specific principle (e.g., "SRP", "colocation").
        
        Args:
            principle_name: Principle name or acronym
        """
        # Map common acronyms
        principle_map = {
            "srp": "Single Responsibility Principle",
            "ocp": "Open/Closed Principle",
            "lsp": "Liskov Substitution Principle",
            "isp": "Interface Segregation Principle",
            "dip": "Dependency Inversion Principle",
        }
        
        search_term = principle_map.get(principle_name.lower(), principle_name)
        
        # Search in principles documents
        result = get_doc_by_id(self.docs_dir, "backend-principles")
        if result:
            _, _, content = result
            # Extract relevant section
            lines = content.split("\n")
            in_section = False
            section_lines = []
            
            for line in lines:
                if search_term.lower() in line.lower() and "#" in line:
                    in_section = True
                    section_lines.append(line)
                elif in_section:
                    if line.startswith("###") or line.startswith("##"):
                        break
                    section_lines.append(line)
            
            if section_lines:
                return "\n".join(section_lines)
        
        # Try frontend principles
        result = get_doc_by_id(self.docs_dir, "frontend-principles")
        if result:
            _, _, content = result
            if search_term.lower() in content.lower():
                return f"Found in frontend principles:\n\n{content}"
        
        return f"Principle '{principle_name}' not found. Available: {', '.join(principle_map.keys())}"
    
    def check_layer_violation(
        self,
        code: str,
        layer: Literal["presentation", "application", "domain", "infrastructure"]
    ) -> dict:
        """Check if code violates layer boundaries.
        
        Args:
            code: Code to check
            layer: Layer name
        
        Returns:
            Dict with is_valid, violations, and suggestions
        """
        return validate_layer_compliance(code, layer)
    
    def check_file_placement(self, file_path: str, stack: Literal["backend", "frontend"]) -> dict:
        """Given a file path, validate it follows structure conventions.
        
        Args:
            file_path: File path to check
            stack: Stack (backend or frontend)
        
        Returns:
            Dict with is_valid and issues
        """
        return validate_file_structure(file_path, stack)
    
    def suggest_pattern(self, use_case: str, stack: Literal["backend", "frontend"]) -> str:
        """Suggest appropriate pattern for a given use case.
        
        Args:
            use_case: Description of the use case
            stack: Stack (backend or frontend)
        """
        use_case_lower = use_case.lower()
        
        suggestions = []
        
        if stack == "backend":
            if any(term in use_case_lower for term in ["stream", "progressive", "real-time", "sse"]):
                suggestions.append("**Streaming Responses** - Use for long-running operations with progressive results")
            if any(term in use_case_lower for term in ["multiple", "provider", "plugin", "factory"]):
                suggestions.append("**Service Registry** - Use for multiple implementations of same interface")
            if any(term in use_case_lower for term in ["dependency", "parallel", "task", "graph"]):
                suggestions.append("**Task Graph Execution** - Use for operations with dependencies between sub-tasks")
            if any(term in use_case_lower for term in ["orchestrate", "coordinate", "workflow", "multi-step"]):
                suggestions.append("**Service Orchestration** - Use for complex operations requiring multiple services")
            if any(term in use_case_lower for term in ["simple", "crud", "fetch", "get"]):
                suggestions.append("**Synchronous Request-Response** - Use for simple operations")
        
        elif stack == "frontend":
            if any(term in use_case_lower for term in ["global", "state", "shared", "context"]):
                suggestions.append("**Context + Consumer Hook** - Use for global state management")
            if any(term in use_case_lower for term in ["server", "api", "fetch", "data"]):
                suggestions.append("**Query Hooks** - Use TanStack Query for server state")
            if any(term in use_case_lower for term in ["update", "mutate", "post", "patch"]):
                suggestions.append("**Mutation Hooks** - Use for data mutations with optimistic updates")
            if any(term in use_case_lower for term in ["stream", "sse", "real-time", "progressive"]):
                suggestions.append("**SSE Hook** - Use for Server-Sent Events streaming")
            if any(term in use_case_lower for term in ["style", "variant", "button", "component"]):
                suggestions.append("**CVA Components** - Use class-variance-authority for styled variants")
        
        if not suggestions:
            return f"No specific pattern suggestion for: {use_case}. Use list_patterns to see all available patterns."
        
        response = f"# Pattern Suggestions for: {use_case}\n\n"
        for suggestion in suggestions:
            response += f"- {suggestion}\n"
        response += "\nUse `get_pattern` with the pattern ID to get detailed information."
        
        return response
    
    def review_component(
        self,
        code: str,
        component_type: str,
        stack: Literal["backend", "frontend"]
    ) -> dict:
        """Review code for architectural compliance.
        
        Args:
            code: Code to review
            component_type: Type of component (e.g., "service", "hook", "controller")
            stack: Stack (backend or frontend)
        
        Returns:
            Dict with compliance_score, issues, and suggestions
        """
        return review_component(code, component_type, stack)
    
    def list_analyzed_repositories(self) -> str:
        """List all successfully analyzed repositories."""
        blueprints_dir = self.storage_dir / "blueprints"
        if not blueprints_dir.exists():
            return "No analyzed repositories found."
            
        repo_ids = [d.name for d in blueprints_dir.iterdir() if d.is_dir() and (d / "backend_blueprint.md").exists()]
        
        if not repo_ids:
            return "No successfully analyzed repositories found."
            
        response = "# Analyzed Repositories\n\n"
        for rid in repo_ids:
            response += f"- **{rid}**\n"
        
        return response
    
    def get_repository_blueprint(self, repo_id: str) -> str:
        """Get the full backend blueprint for a repository."""
        blueprint_file = self.storage_dir / "blueprints" / repo_id / "backend_blueprint.md"
        if not blueprint_file.exists():
            return f"Blueprint for repository '{repo_id}' not found."
            
        return blueprint_file.read_text(encoding='utf-8')
        
    def list_repository_sections(self, repo_id: str) -> str:
        """List all available sections in a repository's blueprint."""
        blueprint_file = self.storage_dir / "blueprints" / repo_id / "backend_blueprint.md"
        if not blueprint_file.exists():
            return f"Blueprint for repository '{repo_id}' not found."
            
        content = blueprint_file.read_text(encoding='utf-8')
        sections = slice_markdown(content)
        
        response = f"# Blueprint Sections for {repo_id}\n\n"
        for section_id in sections.keys():
            response += f"- `{section_id}`\n"
            
        return response
        
    def get_repository_section(self, repo_id: str, section_id: str) -> str:
        """Get a specific section from a repository's blueprint."""
        blueprint_file = self.storage_dir / "blueprints" / repo_id / "backend_blueprint.md"
        if not blueprint_file.exists():
            return f"Blueprint for repository '{repo_id}' not found."
            
        content = blueprint_file.read_text(encoding='utf-8')
        sections = slice_markdown(content)
        
        section_content = sections.get(section_id)
        if not section_content:
            return f"Section '{section_id}' not found in blueprint for '{repo_id}'. Available sections: {', '.join(sections.keys())}"
            
        return section_content

