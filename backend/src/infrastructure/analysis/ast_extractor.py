"""AST extractor for code analysis."""
from pathlib import Path
from typing import Any
import tree_sitter_python as tspython
import tree_sitter_javascript as tsjavascript
import tree_sitter_typescript as tstypescript
from tree_sitter import Language, Parser


class ASTExtractor:
    """Extracts AST from code files."""

    def __init__(self):
        """Initialize AST extractor."""
        # Initialize parsers for different languages
        self._parsers = {
            ".py": self._create_parser("python"),
            ".js": self._create_parser("javascript"),
            ".jsx": self._create_parser("javascript"),
            ".ts": self._create_parser("typescript"),
            ".tsx": self._create_parser("typescript"),
        }

    def _create_parser(self, language: str) -> Parser:
        """Create parser for language."""
        if language == "python":
            return Parser(Language(tspython.language()))
        elif language == "javascript":
            return Parser(Language(tsjavascript.language()))
        elif language == "typescript":
            # tree-sitter-typescript has separate language functions
            return Parser(Language(tstypescript.language_typescript()))
        else:
            return Parser()

    async def extract_all(self, repo_path: Path) -> dict[str, Any]:
        """Extract AST from all code files."""
        ast_data = {
            "files": {},
            "imports": {},
            "exports": {},
            "functions": {},
            "classes": {},
        }
        
        code_files = self._find_code_files(repo_path)
        
        for file_path in code_files:
            try:
                file_ast = await self._extract_file_ast(file_path, repo_path)
                relative_path = str(file_path.relative_to(repo_path))
                ast_data["files"][relative_path] = file_ast
                
                # Aggregate imports, exports, functions, classes
                if "imports" in file_ast:
                    ast_data["imports"][relative_path] = file_ast["imports"]
                if "exports" in file_ast:
                    ast_data["exports"][relative_path] = file_ast["exports"]
                if "functions" in file_ast:
                    ast_data["functions"][relative_path] = file_ast["functions"]
                if "classes" in file_ast:
                    ast_data["classes"][relative_path] = file_ast["classes"]
            except Exception:
                # Skip files that can't be parsed
                continue
        
        return ast_data

    async def _extract_file_ast(self, file_path: Path, repo_path: Path) -> dict[str, Any]:
        """Extract AST from a single file."""
        ext = file_path.suffix
        parser = self._parsers.get(ext)
        
        if not parser:
            return {}
        
        content = file_path.read_text(encoding="utf-8", errors="ignore")
        tree = parser.parse(bytes(content, "utf8"))
        
        return {
            "imports": self._extract_imports(tree, content),
            "exports": self._extract_exports(tree, content),
            "functions": self._extract_functions(tree, content),
            "classes": self._extract_classes(tree, content),
        }

    def _find_code_files(self, repo_path: Path, discovery_ignored_dirs: set[str] | None = None) -> list[Path]:
        """Find all code files, skipping ignored directories."""
        code_extensions = {".py", ".js", ".ts", ".tsx", ".jsx"}
        ignore_patterns = discovery_ignored_dirs or set()
        code_files = []
        for ext in code_extensions:
            for file_path in repo_path.rglob(f"*{ext}"):
                if any(part in ignore_patterns for part in file_path.relative_to(repo_path).parts):
                    continue
                code_files.append(file_path)
        return code_files

    def _extract_imports(self, tree, content: str) -> list[str]:
        """Extract import statements."""
        imports = []
        # Simplified - would traverse AST properly
        return imports

    def _extract_exports(self, tree, content: str) -> list[str]:
        """Extract export statements."""
        exports = []
        # Simplified - would traverse AST properly
        return exports

    def _extract_functions(self, tree, content: str) -> list[dict[str, Any]]:
        """Extract function definitions."""
        functions = []
        # Simplified - would traverse AST properly
        return functions

    def _extract_classes(self, tree, content: str) -> list[dict[str, Any]]:
        """Extract class definitions."""
        classes = []
        # Simplified - would traverse AST properly
        return classes


