"""Structure analyzer."""
from pathlib import Path
from typing import Any

from domain.entities.analysis_settings import SEED_IGNORED_DIRS


class StructureAnalyzer:
    """Analyzes repository file structure and technology stack."""

    def __init__(self):
        """Initialize structure analyzer."""
        pass

    async def analyze(self, repo_path: Path, discovery_ignored_dirs: set[str] | None = None) -> dict[str, Any]:
        """Analyze repository structure."""
        # Resolve path to absolute
        repo_path = Path(repo_path).resolve()

        structure = {
            "file_tree": [],
            "technologies": [],
            "directory_structure": {},
        }

        # Verify path before processing
        if not repo_path.exists():
            import logging
            logging.error(f"Structure analyzer: Path does not exist: {repo_path}")
            return structure

        if not repo_path.is_dir():
            import logging
            logging.error(f"Structure analyzer: Path is not a directory: {repo_path}")
            return structure

        # Check what's actually in the directory
        try:
            items = list(repo_path.iterdir())
            import logging
            logging.info(f"Structure analyzer: Found {len(items)} items in {repo_path}")
            if items:
                sample = [item.name for item in items[:5]]
                logging.info(f"Structure analyzer: Sample items: {sample}")
        except Exception as e:
            import logging
            logging.error(f"Structure analyzer: Cannot list directory {repo_path}: {e}")

        # Build file tree
        structure["file_tree"] = self._build_file_tree(repo_path, discovery_ignored_dirs=discovery_ignored_dirs)
        
        import logging
        logging.info(f"Structure analyzer: Built file tree with {len(structure['file_tree'])} items")

        # Detect technologies
        structure["technologies"] = self._detect_technologies(repo_path)

        # Analyze directory structure
        structure["directory_structure"] = self._analyze_directories(repo_path)

        return structure

    def _build_file_tree(self, repo_path: Path, max_depth: int = 5, discovery_ignored_dirs: set[str] | None = None) -> list[dict[str, Any]]:
        """Build file tree structure."""
        tree = []
        
        # Verify repo_path exists and is a directory
        repo_path = Path(repo_path).resolve()
        if not repo_path.exists():
            import logging
            logging.warning(f"Repository path does not exist: {repo_path}")
            return tree
        if not repo_path.is_dir():
            import logging
            logging.warning(f"Repository path is not a directory: {repo_path}")
            return tree
        
        ignored = discovery_ignored_dirs or set()
        items_checked = 0
        items_added = 0
        items_skipped_hidden = 0
        items_skipped_errors = 0

        def walk_dir(path: Path, depth: int = 0):
            nonlocal items_checked, items_added, items_skipped_hidden, items_skipped_errors
            if depth > max_depth:
                return

            try:
                items = list(path.iterdir())
                for item in items:
                    items_checked += 1

                    # Skip hidden files/folders except .git
                    if item.name.startswith(".") and item.name != ".git":
                        items_skipped_hidden += 1
                        continue

                    # Skip discovery ignored directories
                    if item.is_dir() and item.name in ignored:
                        items_skipped_hidden += 1
                        continue
                    
                    try:
                        # Ensure item is relative to repo_path
                        try:
                            rel_path = item.relative_to(repo_path)
                        except ValueError:
                            # Item is outside repo_path (shouldn't happen, but handle it)
                            items_skipped_errors += 1
                            continue
                        
                        node = {
                            "name": item.name,
                            "path": str(rel_path),
                            "type": "directory" if item.is_dir() else "file",
                        }
                        
                        if item.is_file():
                            try:
                                node["size"] = item.stat().st_size
                                node["extension"] = item.suffix
                            except (OSError, PermissionError):
                                # Skip files we can't read
                                items_skipped_errors += 1
                                continue
                        
                        tree.append(node)
                        items_added += 1
                        
                        # Recursively walk directories
                        if item.is_dir() and depth < max_depth:
                            walk_dir(item, depth + 1)
                    except (OSError, PermissionError):
                        # Skip items we can't access
                        items_skipped_errors += 1
                        continue
                    except Exception as e:
                        # Log unexpected errors for debugging
                        import logging
                        logging.warning(f"Unexpected error processing {item}: {e}")
                        items_skipped_errors += 1
                        continue
            except (PermissionError, OSError) as e:
                # Directory not readable
                import logging
                logging.warning(f"Cannot read directory {path}: {e}")
            except Exception as e:
                # Log unexpected errors
                import logging
                logging.error(f"Unexpected error in walk_dir for {path}: {e}", exc_info=True)
        
        try:
            walk_dir(repo_path)
            
            # Log summary for debugging
            import logging
            logging.debug(
                f"Structure analyzer: checked={items_checked}, added={items_added}, "
                f"skipped_hidden={items_skipped_hidden}, skipped_errors={items_skipped_errors}"
            )
            
            if items_checked > 0 and items_added == 0:
                logging.warning(
                    f"Structure analyzer found {items_checked} items but added 0 to tree. "
                    f"All items may be hidden or inaccessible. Path: {repo_path}"
                )
        except Exception as e:
            # If root directory can't be read, log it
            import logging
            logging.error(f"Cannot read root directory {repo_path}: {e}", exc_info=True)
        
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


