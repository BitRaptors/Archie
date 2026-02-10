"""Tool implementations for querying and validating architecture."""
import fnmatch
import json
import re
from pathlib import Path
from typing import Any, Literal, Optional

from domain.entities.blueprint import StructuredBlueprint

from .resources import BlueprintResources
from .utils.markdown import get_doc_by_id, slice_markdown
from .validators import review_component, validate_file_structure, validate_layer_compliance


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
    
    def _resolve_repo_display_name(self, repo_id: str) -> str:
        """Resolve a human-readable name for a repository from blueprint.json."""
        bp = self._load_structured_blueprint(repo_id)
        if bp and bp.meta.repository:
            return bp.meta.repository
        return repo_id

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
    
    def get_repository_blueprint(self, repo_id: str) -> str:
        """Get the full backend blueprint for a repository (rendered from JSON)."""
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
        sections = slice_markdown(content)
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
        sections = slice_markdown(content)

        section_content = sections.get(section_id)
        if not section_content:
            return (
                f"Section '{section_id}' not found in blueprint for '{repo_id}'. "
                f"Available sections: {', '.join(sections.keys())}"
            )
        return section_content

    # ── Structured Blueprint Tools ────────────────────────────────────

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

    def validate_import(self, repo_id: str, source_file: str, target_import: str) -> str:
        """Check whether an import is allowed by the architecture rules.

        Args:
            repo_id: Repository ID
            source_file: File that contains the import (e.g. "src/api/routes/users.py")
            target_import: Module being imported (e.g. "src/infrastructure/db")

        Returns:
            Human-readable validation result (also machine-parseable JSON at the end).
        """
        bp = self._load_structured_blueprint(repo_id)
        if not bp:
            return f"No structured blueprint found for repository '{repo_id}'. Run analysis first."

        violations: list[dict] = []
        allowed_by: list[str] = []

        for dc in bp.architecture_rules.dependency_constraints:
            if not dc.source_pattern:
                continue

            # Check if the source file matches the constraint's source pattern
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

        # Build response
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
            f"**NO RULE** — No dependency constraint covers `{source_file}` → `{target_import}`.\n"
            f"The import is not explicitly allowed or forbidden.\n"
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
            # Fuzzy: list available component types
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

            # Try regex match if the pattern looks like a regex
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
                    # Heuristic matching for non-regex patterns
                    matches.append({
                        "scope": nc.scope,
                        "pattern": nc.pattern,
                        "description": nc.description,
                        "examples": nc.examples,
                    })
            except re.error:
                # Not a valid regex, just include it as info
                matches.append({
                    "scope": nc.scope,
                    "pattern": nc.pattern,
                    "description": nc.description,
                    "examples": nc.examples,
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


class ArchitectureTools:
    """Tools for architecture enforcement and validation.
    
    These tools work with the learned and reference architecture system
    to provide AI agents with architecture guidance and validation.
    """
    
    def __init__(
        self,
        resolver=None,
        validator=None,
        generator=None,
    ):
        """Initialize architecture tools.
        
        Args:
            resolver: ArchitectureResolver instance
            validator: ArchitectureValidator instance
            generator: AgentFileGenerator instance
        """
        self._resolver = resolver
        self._validator = validator
        self._generator = generator
    
    async def get_architecture_for_repo(
        self,
        repository_id: str,
        section: Optional[str] = None,
    ) -> dict[str, Any]:
        """Get the full resolved architecture for a repository.
        
        Combines reference architecture (if configured) with learned architecture
        according to the repository's merge strategy.
        
        Args:
            repository_id: ID of the repository
            section: Optional section to retrieve (all, layers, patterns, locations, principles)
        
        Returns:
            Dictionary with architecture rules
        """
        if not self._resolver:
            return {"error": "Architecture resolver not configured"}
        
        try:
            architecture = await self._resolver.get_rules_for_repository(repository_id)
            
            if section and section != "all":
                # Filter by section/rule type
                section_to_type = {
                    "layers": "layer",
                    "patterns": "pattern",
                    "locations": "location",
                    "principles": "principle",
                    "dependencies": "dependency",
                    "conventions": "convention",
                    "boundaries": "boundary",
                }
                
                rule_type = section_to_type.get(section)
                if rule_type:
                    rules = architecture.get_rules_by_type(rule_type)
                    return {
                        "repository_id": repository_id,
                        "section": section,
                        "rules_count": len(rules),
                        "rules": [r.to_dict() for r in rules],
                    }
            
            # Return full architecture
            return architecture.to_dict()
            
        except Exception as e:
            return {"error": str(e)}
    
    async def validate_code(
        self,
        repository_id: str,
        file_path: str,
        code_content: str,
    ) -> dict[str, Any]:
        """Validate code against architecture rules before writing.
        
        Use this tool to check if proposed code follows the architecture
        rules for a repository.
        
        Args:
            repository_id: ID of the repository
            file_path: Proposed file path
            code_content: Code content to validate
        
        Returns:
            Dictionary with validation result
        """
        if not self._validator:
            return {"error": "Architecture validator not configured"}
        
        try:
            result = await self._validator.validate_file(
                repository_id=repository_id,
                file_path=file_path,
                content=code_content,
            )
            
            return result.to_dict()
            
        except Exception as e:
            return {"error": str(e)}
    
    async def check_file_location(
        self,
        repository_id: str,
        file_path: str,
    ) -> dict[str, Any]:
        """Check if a proposed file path follows architecture conventions.
        
        Use this tool before creating new files to ensure they're in the
        correct location.
        
        Args:
            repository_id: ID of the repository
            file_path: Proposed file path
        
        Returns:
            Dictionary with location check result
        """
        if not self._validator:
            return {"error": "Architecture validator not configured"}
        
        try:
            result = await self._validator.check_file_location(
                repository_id=repository_id,
                file_path=file_path,
            )
            
            return {
                "file_path": file_path,
                "is_valid": result.is_valid,
                "violations": [v.to_dict() for v in result.violations],
                "suggestion": result.violations[0].suggestion if result.violations else None,
            }
            
        except Exception as e:
            return {"error": str(e)}
    
    async def get_implementation_guide(
        self,
        repository_id: str,
        feature_type: str,
    ) -> dict[str, Any]:
        """Get step-by-step implementation guide for a feature type.
        
        Provides guidance on where to place files and what patterns to use
        based on the repository's architecture.
        
        Args:
            repository_id: ID of the repository
            feature_type: Type of feature (e.g., "api_endpoint", "service", "entity")
        
        Returns:
            Dictionary with implementation steps
        """
        if not self._resolver:
            return {"error": "Architecture resolver not configured"}
        
        try:
            architecture = await self._resolver.get_rules_for_repository(repository_id)
            
            # Build implementation guide based on architecture rules
            guide = {
                "feature_type": feature_type,
                "steps": [],
                "file_locations": [],
                "patterns_to_use": [],
                "imports_allowed": [],
                "imports_forbidden": [],
            }
            
            # Get relevant location rules
            location_rules = architecture.get_rules_by_type("location")
            for rule in location_rules:
                purpose = rule.rule_data.get("purpose", "").lower()
                path = rule.rule_data.get("path", "")
                
                # Match feature type to locations
                type_lower = feature_type.lower()
                if type_lower in purpose or type_lower in path.lower():
                    guide["file_locations"].append({
                        "path": path,
                        "purpose": rule.rule_data.get("purpose", ""),
                    })
            
            # Get relevant patterns
            pattern_rules = architecture.get_pattern_rules()
            for rule in pattern_rules:
                usage = rule.rule_data.get("usage", "").lower()
                if feature_type.lower() in usage or feature_type.lower() in rule.name.lower():
                    guide["patterns_to_use"].append({
                        "pattern": rule.name,
                        "description": rule.description,
                    })
            
            # Get dependency rules
            dep_rules = architecture.get_dependency_rules()
            for rule in dep_rules:
                allowed = rule.rule_data.get("allowed_imports", [])
                forbidden = rule.rule_data.get("forbidden_imports", [])
                guide["imports_allowed"].extend(allowed)
                guide["imports_forbidden"].extend(forbidden)
            
            # Build steps
            if guide["file_locations"]:
                loc = guide["file_locations"][0]
                guide["steps"].append(f"1. Create file in: {loc['path']}")
            
            if guide["patterns_to_use"]:
                pattern = guide["patterns_to_use"][0]
                guide["steps"].append(f"2. Follow pattern: {pattern['pattern']}")
            
            if guide["imports_allowed"]:
                guide["steps"].append(f"3. Import from: {', '.join(guide['imports_allowed'][:5])}")
            
            if guide["imports_forbidden"]:
                guide["steps"].append(f"4. Do NOT import from: {', '.join(guide['imports_forbidden'][:5])}")
            
            return guide
            
        except Exception as e:
            return {"error": str(e)}
    
    async def configure_architecture(
        self,
        repository_id: str,
        reference_blueprint_id: Optional[str] = None,
        merge_strategy: str = "learned_primary",
    ) -> dict[str, Any]:
        """Configure architecture sources for a repository.
        
        Args:
            repository_id: ID of the repository
            reference_blueprint_id: Optional blueprint to use as reference
            merge_strategy: How to merge rules (learned_primary, reference_primary, etc.)
        
        Returns:
            Configuration result
        """
        if not self._resolver:
            return {"error": "Architecture resolver not configured"}
        
        try:
            config = await self._resolver.configure_repository(
                repository_id=repository_id,
                reference_blueprint_id=reference_blueprint_id,
                merge_strategy=merge_strategy,
            )
            
            return {
                "repository_id": config.repository_id,
                "reference_blueprint_id": config.reference_blueprint_id,
                "use_learned_architecture": config.use_learned_architecture,
                "merge_strategy": config.merge_strategy,
            }
            
        except Exception as e:
            return {"error": str(e)}
    
    async def list_reference_blueprints(self) -> dict[str, Any]:
        """List all available reference architecture blueprints.
        
        Returns:
            List of available blueprint IDs
        """
        if not self._resolver:
            return {"error": "Architecture resolver not configured"}
        
        try:
            blueprints = await self._resolver._architecture_rule_repo.list_blueprints()
            
            return {
                "blueprints": blueprints,
                "count": len(blueprints),
            }
            
        except Exception as e:
            return {"error": str(e)}
    
    async def generate_claude_md(
        self,
        repository_id: str,
        repository_name: str,
    ) -> dict[str, Any]:
        """Generate CLAUDE.md content for a repository.
        
        Args:
            repository_id: Repository ID
            repository_name: Human-readable name
        
        Returns:
            Generated CLAUDE.md content
        """
        if not self._resolver or not self._generator:
            return {"error": "Generator not configured"}
        
        try:
            architecture = await self._resolver.get_rules_for_repository(repository_id)
            content = await self._generator.generate_claude_md(
                repository_id=repository_id,
                repository_name=repository_name,
                architecture=architecture,
            )
            
            return {
                "repository_id": repository_id,
                "content": content,
            }
            
        except Exception as e:
            return {"error": str(e)}

