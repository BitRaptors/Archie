"""Token scanner for codebase analysis with token counting."""
import fnmatch
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# Default patterns to always ignore (common non-code files)
DEFAULT_IGNORE_PATTERNS = {
    # Directories
    ".git",
    ".svn",
    ".hg",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "venv",
    ".venv",
    "env",
    ".env",
    "dist",
    "build",
    ".next",
    ".nuxt",
    ".output",
    "coverage",
    ".coverage",
    ".nyc_output",
    "target",
    "vendor",
    ".bundle",
    ".cargo",
    # Files
    ".DS_Store",
    "Thumbs.db",
    "*.pyc",
    "*.pyo",
    "*.so",
    "*.dylib",
    "*.dll",
    "*.exe",
    "*.o",
    "*.a",
    "*.lib",
    "*.class",
    "*.jar",
    "*.war",
    "*.egg",
    "*.whl",
    "*.lock",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "bun.lockb",
    "Cargo.lock",
    "poetry.lock",
    "Gemfile.lock",
    "composer.lock",
    # Binary/media
    "*.png",
    "*.jpg",
    "*.jpeg",
    "*.gif",
    "*.ico",
    "*.svg",
    "*.webp",
    "*.mp3",
    "*.mp4",
    "*.wav",
    "*.avi",
    "*.mov",
    "*.pdf",
    "*.zip",
    "*.tar",
    "*.gz",
    "*.rar",
    "*.7z",
    "*.woff",
    "*.woff2",
    "*.ttf",
    "*.eot",
    "*.otf",
    # Large generated files
    "*.min.js",
    "*.min.css",
    "*.map",
    "*.chunk.js",
    "*.bundle.js",
}

# Text file extensions we consider as code
TEXT_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".vue", ".svelte",
    ".html", ".htm", ".css", ".scss", ".sass", ".less",
    ".json", ".yaml", ".yml", ".toml", ".xml",
    ".md", ".mdx", ".txt", ".rst",
    ".sh", ".bash", ".zsh", ".fish", ".ps1", ".bat", ".cmd",
    ".sql", ".graphql", ".gql", ".proto",
    ".go", ".rs", ".rb", ".php", ".java", ".kt", ".kts", ".scala",
    ".clj", ".cljs", ".edn", ".ex", ".exs", ".erl", ".hrl",
    ".hs", ".lhs", ".ml", ".mli", ".fs", ".fsx", ".fsi",
    ".cs", ".vb", ".swift", ".m", ".mm", ".h", ".hpp",
    ".c", ".cpp", ".cc", ".cxx", ".r", ".R", ".jl", ".lua",
    ".vim", ".el", ".lisp", ".scm", ".rkt", ".zig", ".nim",
    ".d", ".dart", ".v", ".sv", ".vhd", ".vhdl",
    ".tf", ".hcl", ".dockerfile", ".containerfile",
    ".makefile", ".cmake", ".gradle", ".groovy",
    ".rake", ".gemspec", ".podspec", ".cabal", ".nix", ".dhall",
    ".jsonc", ".json5", ".cson", ".ini", ".cfg", ".conf", ".config",
    ".gitignore", ".gitattributes", ".editorconfig",
    ".prettierrc", ".eslintrc", ".stylelintrc", ".babelrc",
    ".nvmrc", ".ruby-version", ".python-version", ".node-version",
    ".tool-versions",
}


@dataclass
class FileInfo:
    """Information about a single file."""
    path: str
    tokens: int
    size_bytes: int
    extension: str


@dataclass
class ScanResult:
    """Result of scanning a codebase."""
    root: str
    files: list[FileInfo] = field(default_factory=list)
    directories: list[str] = field(default_factory=list)
    total_tokens: int = 0
    total_files: int = 0
    skipped: list[dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "root": self.root,
            "files": [
                {
                    "path": f.path,
                    "tokens": f.tokens,
                    "size_bytes": f.size_bytes,
                    "extension": f.extension,
                }
                for f in self.files
            ],
            "directories": self.directories,
            "total_tokens": self.total_tokens,
            "total_files": self.total_files,
            "skipped_count": len(self.skipped),
        }


class TokenScanner:
    """Scans codebases with token counting for work distribution.
    
    Token counting is essential for distributing work across workers
    while staying within model context limits.
    """
    
    def __init__(
        self,
        max_file_tokens: int = 50_000,
        max_file_size_bytes: int = 1_000_000,
        encoding_name: str = "cl100k_base",
    ):
        """Initialize token scanner.
        
        Args:
            max_file_tokens: Skip files with more tokens than this
            max_file_size_bytes: Skip files larger than this (bytes)
            encoding_name: Tiktoken encoding name for token counting
        """
        self._max_file_tokens = max_file_tokens
        self._max_file_size_bytes = max_file_size_bytes
        self._encoding_name = encoding_name
        self._encoding = None
        
    def _get_encoding(self):
        """Lazy load tiktoken encoding."""
        if self._encoding is None:
            try:
                import tiktoken
                self._encoding = tiktoken.get_encoding(self._encoding_name)
            except ImportError:
                logger.warning("tiktoken not installed, using character-based estimation")
                self._encoding = None
        return self._encoding
    
    def _count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        encoding = self._get_encoding()
        if encoding:
            try:
                return len(encoding.encode(text))
            except Exception:
                pass
        # Fallback: estimate ~4 chars per token
        return len(text) // 4
    
    def _parse_gitignore(self, root: Path) -> list[str]:
        """Parse .gitignore file and return patterns."""
        gitignore_path = root / ".gitignore"
        patterns = []
        if gitignore_path.exists():
            try:
                with open(gitignore_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        line = line.strip()
                        # Skip comments and empty lines
                        if line and not line.startswith("#"):
                            patterns.append(line)
            except Exception:
                pass
        return patterns
    
    def _should_ignore(self, path: Path, root: Path, gitignore_patterns: list[str]) -> bool:
        """Check if a path should be ignored."""
        name = path.name
        
        # Check default ignores
        for pattern in DEFAULT_IGNORE_PATTERNS:
            if "*" in pattern:
                if fnmatch.fnmatch(name, pattern):
                    return True
            elif name == pattern:
                return True
        
        # Check gitignore patterns
        try:
            rel_path = str(path.relative_to(root))
        except ValueError:
            return True
        
        for pattern in gitignore_patterns:
            # Handle negation (skip for simplicity)
            if pattern.startswith("!"):
                continue
            
            # Handle directory-only patterns
            check_pattern = pattern.rstrip("/")
            
            # Check against name and relative path
            if fnmatch.fnmatch(name, check_pattern):
                return True
            if fnmatch.fnmatch(rel_path, check_pattern):
                return True
            if fnmatch.fnmatch(rel_path, f"**/{check_pattern}"):
                return True
        
        return False
    
    def _is_text_file(self, path: Path) -> bool:
        """Check if a file is likely a text file."""
        # Check by extension
        suffix = path.suffix.lower()
        if suffix in TEXT_EXTENSIONS:
            return True
        
        # Check for extensionless files that are commonly text
        name = path.name.lower()
        text_names = {
            "readme", "license", "licence", "changelog", "authors",
            "contributors", "copying", "dockerfile", "containerfile",
            "makefile", "rakefile", "gemfile", "procfile", "brewfile",
            "vagrantfile", "justfile", "taskfile",
        }
        if name in text_names:
            return True
        
        # Try to detect binary by reading first bytes
        try:
            with open(path, "rb") as f:
                chunk = f.read(8192)
                # Check for null bytes (binary indicator)
                if b"\x00" in chunk:
                    return False
                # Try to decode as UTF-8
                try:
                    chunk.decode("utf-8")
                    return True
                except UnicodeDecodeError:
                    return False
        except Exception:
            return False
    
    async def scan(self, root: Path) -> ScanResult:
        """Scan a directory and return file information with token counts.
        
        Args:
            root: Root directory to scan
            
        Returns:
            ScanResult with file information and token counts
        """
        root = Path(root).resolve()
        gitignore_patterns = self._parse_gitignore(root)
        
        result = ScanResult(root=str(root))
        
        def walk_dir(current: Path, depth: int = 0):
            if depth > 10:  # Max depth to prevent infinite loops
                return
            
            if self._should_ignore(current, root, gitignore_patterns):
                return
            
            if current.is_dir():
                try:
                    rel_path = str(current.relative_to(root))
                    if rel_path != ".":
                        result.directories.append(rel_path)
                except ValueError:
                    return
                
                try:
                    entries = sorted(current.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
                    for entry in entries:
                        walk_dir(entry, depth + 1)
                except PermissionError:
                    result.skipped.append({"path": str(current), "reason": "permission_denied"})
                except Exception as e:
                    result.skipped.append({"path": str(current), "reason": str(e)})
            
            elif current.is_file():
                try:
                    rel_path = str(current.relative_to(root))
                except ValueError:
                    return
                
                try:
                    size_bytes = current.stat().st_size
                except (OSError, PermissionError):
                    result.skipped.append({"path": rel_path, "reason": "cannot_stat"})
                    return
                
                # Skip very large files
                if size_bytes > self._max_file_size_bytes:
                    result.skipped.append({
                        "path": rel_path,
                        "reason": "too_large",
                        "size_bytes": size_bytes,
                    })
                    return
                
                # Skip binary files
                if not self._is_text_file(current):
                    result.skipped.append({"path": rel_path, "reason": "binary"})
                    return
                
                try:
                    with open(current, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    
                    tokens = self._count_tokens(content)
                    
                    if tokens > self._max_file_tokens:
                        result.skipped.append({
                            "path": rel_path,
                            "reason": "too_many_tokens",
                            "tokens": tokens,
                        })
                        return
                    
                    file_info = FileInfo(
                        path=rel_path,
                        tokens=tokens,
                        size_bytes=size_bytes,
                        extension=current.suffix,
                    )
                    result.files.append(file_info)
                    result.total_tokens += tokens
                    result.total_files += 1
                    
                except Exception as e:
                    result.skipped.append({"path": rel_path, "reason": f"read_error: {str(e)}"})
        
        walk_dir(root)
        
        logger.info(
            f"Scanned {result.total_files} files, {result.total_tokens:,} tokens, "
            f"skipped {len(result.skipped)} files"
        )
        
        return result
    
    def plan_assignments(
        self,
        scan_result: ScanResult,
        budget_per_worker: int = 150_000,
        min_files_per_worker: int = 1,
    ) -> list[list[str]]:
        """Plan how to distribute files across workers based on token budgets.
        
        Args:
            scan_result: Result from scan()
            budget_per_worker: Max tokens per worker
            min_files_per_worker: Minimum files per worker
            
        Returns:
            List of file path lists, one per worker
        """
        if not scan_result.files:
            return []
        
        # Sort files by directory to keep related files together
        sorted_files = sorted(scan_result.files, key=lambda f: f.path)
        
        assignments: list[list[str]] = []
        current_assignment: list[str] = []
        current_tokens = 0
        
        for file_info in sorted_files:
            # If adding this file would exceed budget, start new assignment
            if current_tokens + file_info.tokens > budget_per_worker and current_assignment:
                assignments.append(current_assignment)
                current_assignment = []
                current_tokens = 0
            
            current_assignment.append(file_info.path)
            current_tokens += file_info.tokens
        
        # Don't forget the last assignment
        if current_assignment:
            assignments.append(current_assignment)
        
        # Merge small assignments if possible
        merged_assignments: list[list[str]] = []
        i = 0
        while i < len(assignments):
            current = assignments[i]
            current_token_sum = sum(
                f.tokens for f in scan_result.files if f.path in current
            )
            
            # Try to merge with next assignment if both are small
            if i + 1 < len(assignments):
                next_assignment = assignments[i + 1]
                next_token_sum = sum(
                    f.tokens for f in scan_result.files if f.path in next_assignment
                )
                
                if current_token_sum + next_token_sum <= budget_per_worker:
                    merged_assignments.append(current + next_assignment)
                    i += 2
                    continue
            
            merged_assignments.append(current)
            i += 1
        
        logger.info(
            f"Planned {len(merged_assignments)} worker assignments from "
            f"{scan_result.total_files} files"
        )
        
        return merged_assignments
