"""Hierarchical directory summarization for codebase understanding."""
from pathlib import Path
from typing import Any
from anthropic import AsyncAnthropic
from config.settings import get_settings


class DirectorySummarizer:
    """Generates hierarchical summaries of directories.
    
    This provides multi-level understanding:
    1. File-level: Individual file purposes
    2. Directory-level: Module/package purposes
    3. Layer-level: Architectural layer purposes
    
    The summaries are generated bottom-up and can be used for:
    - Quick understanding of large codebases
    - Context for AI analysis phases
    - Navigation aids in generated blueprints
    """

    def __init__(self, supabase_client=None):
        """Initialize directory summarizer.
        
        Args:
            supabase_client: Supabase client for caching summaries
        """
        settings = get_settings()
        self._client = AsyncAnthropic(api_key=settings.anthropic_api_key) if settings.anthropic_api_key else None
        self._model = settings.default_ai_model
        self._supabase_client = supabase_client
        self._cache: dict[str, str] = {}

    async def summarize_repository(
        self,
        repo_path: Path,
        repository_id: str | None = None,
        discovery_ignored_dirs: set[str] | None = None,
    ) -> dict[str, Any]:
        """Generate hierarchical summary of entire repository.

        Args:
            repo_path: Path to the cloned repository
            repository_id: UUID for caching (optional)
            discovery_ignored_dirs: User-configured directories to skip.

        Returns:
            Hierarchical summary structure
        """
        self._discovery_ignored_dirs = discovery_ignored_dirs
        summary = {
            "overview": "",
            "directories": {},
            "key_modules": [],
            "architecture_hints": [],
        }
        
        # Get top-level directories
        top_dirs = [d for d in repo_path.iterdir() if d.is_dir() and not d.name.startswith('.')]
        
        # Summarize each top-level directory
        for directory in top_dirs:
            if self._should_skip_directory(directory.name):
                continue
            
            dir_summary = await self._summarize_directory(directory, repo_path)
            summary["directories"][directory.name] = dir_summary
            
            # Track key modules
            if dir_summary.get("is_key_module"):
                summary["key_modules"].append({
                    "name": directory.name,
                    "purpose": dir_summary.get("purpose", "Unknown"),
                    "type": dir_summary.get("type", "module"),
                })
        
        # Generate overview
        summary["overview"] = await self._generate_overview(summary["directories"])
        
        # Extract architecture hints
        summary["architecture_hints"] = self._extract_architecture_hints(summary["directories"])
        
        return summary

    async def _summarize_directory(
        self,
        directory: Path,
        repo_root: Path,
        depth: int = 0,
    ) -> dict[str, Any]:
        """Summarize a single directory.
        
        Args:
            directory: Path to directory
            repo_root: Root of repository
            depth: Current recursion depth
            
        Returns:
            Directory summary
        """
        if depth > 3:  # Limit recursion depth
            return {"purpose": "Nested module", "files": [], "type": "nested"}
        
        summary = {
            "purpose": "",
            "type": "unknown",
            "files": [],
            "subdirectories": {},
            "is_key_module": False,
        }
        
        # Get files in directory
        files = []
        code_files = []
        for item in directory.iterdir():
            if item.is_file():
                files.append(item.name)
                if self._is_code_file(item.name):
                    code_files.append(item)
        
        summary["files"] = files[:20]  # Limit for large directories
        
        # Get subdirectories
        subdirs = [d for d in directory.iterdir() if d.is_dir() and not d.name.startswith('.')]
        
        for subdir in subdirs:
            if self._should_skip_directory(subdir.name):
                continue
            subdir_summary = await self._summarize_directory(subdir, repo_root, depth + 1)
            summary["subdirectories"][subdir.name] = subdir_summary
        
        # Determine directory type and purpose
        relative_path = str(directory.relative_to(repo_root))
        summary["type"] = self._detect_directory_type(directory.name, files)
        summary["purpose"] = await self._infer_purpose(
            directory.name,
            files,
            code_files[:5],  # Sample a few files
            summary["type"],
        )
        summary["is_key_module"] = self._is_key_module(directory.name, summary["type"], len(code_files))
        
        return summary

    async def _infer_purpose(
        self,
        dir_name: str,
        files: list[str],
        code_files: list[Path],
        dir_type: str,
    ) -> str:
        """Infer the purpose of a directory.
        
        Args:
            dir_name: Name of the directory
            files: List of files in directory
            code_files: Sample code files to analyze
            dir_type: Detected directory type
            
        Returns:
            Purpose description
        """
        # Known directory patterns
        known_purposes = {
            "api": "API endpoints and route definitions",
            "routes": "HTTP route handlers",
            "controllers": "Request/response handling",
            "services": "Business logic and orchestration",
            "application": "Application layer services",
            "domain": "Domain entities and business rules",
            "entities": "Domain model definitions",
            "models": "Data models and schemas",
            "infrastructure": "External integrations and implementations",
            "persistence": "Data storage and retrieval",
            "repositories": "Repository pattern implementations",
            "config": "Configuration and settings",
            "utils": "Utility functions and helpers",
            "helpers": "Helper functions",
            "lib": "Shared library code",
            "core": "Core application functionality",
            "components": "UI components",
            "pages": "Page components or views",
            "views": "View templates or components",
            "hooks": "React/Vue hooks",
            "context": "React context providers",
            "store": "State management",
            "tests": "Test files",
            "test": "Test files",
            "__tests__": "Test files",
            "migrations": "Database migrations",
            "scripts": "Build and utility scripts",
            "workers": "Background workers and tasks",
            "events": "Event handlers and publishers",
            "middleware": "Request/response middleware",
            "dto": "Data transfer objects",
            "schemas": "Validation schemas",
            "types": "Type definitions",
        }
        
        # Check for known patterns
        dir_lower = dir_name.lower()
        if dir_lower in known_purposes:
            return known_purposes[dir_lower]
        
        # Check partial matches
        for pattern, purpose in known_purposes.items():
            if pattern in dir_lower:
                return purpose
        
        # For unknown directories, analyze file names
        if files:
            file_hints = self._analyze_file_names(files)
            if file_hints:
                return file_hints
        
        # Use AI for complex cases (if available and worthwhile)
        if self._client and code_files and len(code_files) >= 2:
            return await self._ai_infer_purpose(dir_name, files, code_files[:3])
        
        return f"{dir_type.capitalize()} module"

    async def _ai_infer_purpose(
        self,
        dir_name: str,
        files: list[str],
        code_files: list[Path],
    ) -> str:
        """Use AI to infer directory purpose from code samples.
        
        Args:
            dir_name: Name of the directory
            files: List of files
            code_files: Sample code files
            
        Returns:
            AI-inferred purpose
        """
        # Read sample code
        code_samples = []
        for code_file in code_files:
            try:
                content = code_file.read_text(encoding="utf-8", errors="ignore")
                lines = content.splitlines()[:50]  # First 50 lines
                code_samples.append(f"**{code_file.name}:**\n```\n{chr(10).join(lines)}\n```")
            except Exception:
                continue
        
        if not code_samples:
            return "Unknown module"
        
        prompt = f"""Analyze this directory and provide a ONE SENTENCE purpose description.

Directory: {dir_name}
Files: {', '.join(files[:10])}

Sample Code:
{chr(10).join(code_samples)}

Respond with ONLY the purpose (one sentence, no quotes):"""

        try:
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=100,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text.strip()
        except Exception:
            return "Application module"

    async def _generate_overview(self, directories: dict[str, Any]) -> str:
        """Generate overall repository overview from directory summaries.
        
        Args:
            directories: Dictionary of directory summaries
            
        Returns:
            Overview text
        """
        if not directories:
            return "Repository structure unclear"
        
        # Build overview from directory purposes
        parts = []
        for dir_name, summary in directories.items():
            purpose = summary.get("purpose", "Unknown")
            parts.append(f"- **{dir_name}/**: {purpose}")
        
        return "\n".join(parts)

    def _extract_architecture_hints(self, directories: dict[str, Any]) -> list[str]:
        """Extract architecture hints from directory structure.
        
        Args:
            directories: Dictionary of directory summaries
            
        Returns:
            List of architecture hints
        """
        hints = []
        dir_names = set(directories.keys())
        
        # Check for layered architecture
        layered_indicators = {"api", "application", "domain", "infrastructure"}
        if len(layered_indicators & {d.lower() for d in dir_names}) >= 3:
            hints.append("Follows Clean Architecture / Layered Architecture pattern")
        
        # Check for frontend framework
        if "components" in dir_names or "pages" in dir_names:
            hints.append("Component-based frontend structure (React/Vue/etc.)")
        
        # Check for microservices patterns
        if "services" in dir_names and "workers" in dir_names:
            hints.append("Service-oriented with background workers")
        
        # Check for DDD patterns
        if "domain" in dir_names and "entities" in {d.lower() for d in directories.get("domain", {}).get("subdirectories", {}).keys()}:
            hints.append("Domain-Driven Design patterns present")
        
        # Check for API-first
        if "api" in dir_names or "routes" in dir_names:
            hints.append("API-first design with dedicated routing layer")
        
        return hints

    def _detect_directory_type(self, dir_name: str, files: list[str]) -> str:
        """Detect the type of a directory.
        
        Args:
            dir_name: Name of the directory
            files: Files in the directory
            
        Returns:
            Directory type string
        """
        dir_lower = dir_name.lower()
        
        # Check directory name patterns
        if any(x in dir_lower for x in ["test", "__test__", "spec"]):
            return "test"
        if any(x in dir_lower for x in ["api", "route", "endpoint"]):
            return "api"
        if any(x in dir_lower for x in ["service", "application"]):
            return "service"
        if any(x in dir_lower for x in ["model", "entity", "domain"]):
            return "domain"
        if any(x in dir_lower for x in ["repo", "persist", "database"]):
            return "persistence"
        if any(x in dir_lower for x in ["config", "setting"]):
            return "config"
        if any(x in dir_lower for x in ["util", "helper", "lib"]):
            return "utility"
        if any(x in dir_lower for x in ["component", "page", "view"]):
            return "ui"
        if any(x in dir_lower for x in ["infra", "external"]):
            return "infrastructure"
        
        # Check file patterns
        if any(f.endswith(('.tsx', '.jsx')) for f in files):
            return "component"
        if any(f.endswith('_test.py') or f.endswith('.test.ts') for f in files):
            return "test"
        
        return "module"

    def _should_skip_directory(self, dir_name: str) -> bool:
        """Check if a directory should be skipped.

        Uses user-configured ignored dirs from DB when available,
        falls back to DEFAULT_IGNORED_DIRS.

        Args:
            dir_name: Name of the directory

        Returns:
            True if should skip
        """
        from domain.entities.analysis_settings import DEFAULT_IGNORED_DIRS

        ignored = getattr(self, "_discovery_ignored_dirs", None) or DEFAULT_IGNORED_DIRS
        return dir_name in ignored or dir_name.startswith('.')

    def _is_code_file(self, filename: str) -> bool:
        """Check if a file is a code file.
        
        Args:
            filename: Name of the file
            
        Returns:
            True if code file
        """
        code_extensions = {
            ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".rs",
            ".cpp", ".c", ".h", ".hpp", ".cs", ".rb", ".php", ".swift",
        }
        return any(filename.endswith(ext) for ext in code_extensions)

    def _is_key_module(self, dir_name: str, dir_type: str, code_file_count: int) -> bool:
        """Determine if a directory is a key module.
        
        Args:
            dir_name: Name of the directory
            dir_type: Detected type
            code_file_count: Number of code files
            
        Returns:
            True if key module
        """
        key_types = {"api", "service", "domain", "persistence", "component"}
        return dir_type in key_types and code_file_count >= 2

    def _analyze_file_names(self, files: list[str]) -> str:
        """Analyze file names to infer purpose.
        
        Args:
            files: List of file names
            
        Returns:
            Inferred purpose or empty string
        """
        files_lower = [f.lower() for f in files]
        
        if any("route" in f or "endpoint" in f for f in files_lower):
            return "API routing and endpoints"
        if any("service" in f for f in files_lower):
            return "Business logic services"
        if any("repository" in f or "repo" in f for f in files_lower):
            return "Data access layer"
        if any("model" in f or "entity" in f for f in files_lower):
            return "Data models and entities"
        if any("controller" in f for f in files_lower):
            return "Request handling controllers"
        if any("middleware" in f for f in files_lower):
            return "Request/response middleware"
        if any("hook" in f for f in files_lower):
            return "React/Vue hooks"
        if any("context" in f or "provider" in f for f in files_lower):
            return "State/context providers"
        if any("util" in f or "helper" in f for f in files_lower):
            return "Utility functions"
        
        return ""

