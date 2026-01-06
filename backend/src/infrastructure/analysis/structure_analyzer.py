"""Structure analyzer."""
from pathlib import Path
from typing import Any
import json


class StructureAnalyzer:
    """Analyzes repository file structure and technology stack."""

    def __init__(self):
        """Initialize structure analyzer."""
        pass

    async def analyze(self, repo_path: Path) -> dict[str, Any]:
        """Analyze repository structure."""
        structure = {
            "file_tree": [],
            "technologies": [],
            "directory_structure": {},
        }

        # Build file tree
        structure["file_tree"] = self._build_file_tree(repo_path)

        # Detect technologies
        structure["technologies"] = self._detect_technologies(repo_path)

        # Analyze directory structure
        structure["directory_structure"] = self._analyze_directories(repo_path)

        return structure

    def _build_file_tree(self, repo_path: Path, max_depth: int = 5) -> list[dict[str, Any]]:
        """Build file tree structure."""
        tree = []
        
        def walk_dir(path: Path, depth: int = 0):
            if depth > max_depth:
                return
            
            try:
                for item in path.iterdir():
                    if item.name.startswith(".") and item.name != ".git":
                        continue
                    
                    node = {
                        "name": item.name,
                        "path": str(item.relative_to(repo_path)),
                        "type": "directory" if item.is_dir() else "file",
                    }
                    
                    if item.is_file():
                        node["size"] = item.stat().st_size
                        node["extension"] = item.suffix
                    
                    tree.append(node)
                    
                    if item.is_dir() and depth < max_depth:
                        walk_dir(item, depth + 1)
            except PermissionError:
                pass
        
        walk_dir(repo_path)
        return tree

    def _detect_technologies(self, repo_path: Path) -> list[str]:
        """Detect technology stack from files."""
        technologies = []
        
        # Check for package files
        if (repo_path / "package.json").exists():
            technologies.append("nodejs")
        if (repo_path / "requirements.txt").exists() or (repo_path / "pyproject.toml").exists():
            technologies.append("python")
        if (repo_path / "go.mod").exists():
            technologies.append("go")
        if (repo_path / "Cargo.toml").exists():
            technologies.append("rust")
        if (repo_path / "pom.xml").exists():
            technologies.append("java")
        
        # Check for framework files
        if (repo_path / "next.config.js").exists() or (repo_path / "next.config.ts").exists():
            technologies.append("nextjs")
        if (repo_path / "vue.config.js").exists():
            technologies.append("vue")
        if (repo_path / "angular.json").exists():
            technologies.append("angular")
        if (repo_path / "tsconfig.json").exists():
            technologies.append("typescript")
        
        return technologies

    def _analyze_directories(self, repo_path: Path) -> dict[str, Any]:
        """Analyze directory organization patterns."""
        structure = {
            "root_files": [],
            "src_structure": {},
            "test_structure": {},
        }
        
        # Analyze root level
        for item in repo_path.iterdir():
            if item.is_file() and not item.name.startswith("."):
                structure["root_files"].append(item.name)
        
        # Analyze src/ directory if exists
        src_path = repo_path / "src"
        if src_path.exists():
            structure["src_structure"] = self._analyze_directory_structure(src_path)
        
        # Analyze test directories
        for test_dir in ["tests", "test", "__tests__"]:
            test_path = repo_path / test_dir
            if test_path.exists():
                structure["test_structure"][test_dir] = self._analyze_directory_structure(test_path)
        
        return structure

    def _analyze_directory_structure(self, path: Path) -> dict[str, Any]:
        """Analyze a specific directory structure."""
        structure = {
            "files": [],
            "subdirectories": [],
        }
        
        for item in path.iterdir():
            if item.is_file():
                structure["files"].append(item.name)
            elif item.is_dir():
                structure["subdirectories"].append(item.name)
        
        return structure


