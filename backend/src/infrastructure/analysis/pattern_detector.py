"""Pattern detector combining structural and semantic matching."""
from pathlib import Path
from typing import Any
from infrastructure.analysis.semantic_pattern_finder import SemanticPatternFinder


class PatternDetector:
    """Detects architectural patterns using hybrid approach."""

    def __init__(self, semantic_finder: SemanticPatternFinder):
        """Initialize pattern detector."""
        self._semantic_finder = semantic_finder

    async def detect_patterns(
        self,
        repository_id: str,
        repo_path: Path,
        prompt_config: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Detect patterns using structural and semantic search."""
        patterns = {
            "structural": {},
            "semantic": {},
            "combined": {},
        }
        
        # Structural pattern detection
        patterns["structural"] = await self._detect_structural_patterns(repo_path)
        
        # Semantic pattern detection
        patterns["semantic"] = await self._semantic_finder.find_patterns(
            repository_id=repository_id,
            prompt_config=prompt_config,
        )
        
        # Combine results
        patterns["combined"] = self._combine_patterns(
            patterns["structural"],
            patterns["semantic"],
        )
        
        return patterns

    async def _detect_structural_patterns(self, repo_path: Path) -> dict[str, Any]:
        """Detect patterns using structural analysis (grep, AST)."""
        patterns = {}
        
        # Example: Detect service registry pattern
        patterns["service_registry"] = await self._find_service_registry(repo_path)
        
        # Example: Detect context hook pattern
        patterns["context_hook"] = await self._find_context_hooks(repo_path)
        
        return patterns

    async def _find_service_registry(self, repo_path: Path) -> list[dict[str, Any]]:
        """Find service registry patterns."""
        matches = []
        # Simplified - would use grep/AST to find patterns
        return matches

    async def _find_context_hooks(self, repo_path: Path) -> list[dict[str, Any]]:
        """Find React context hook patterns."""
        matches = []
        # Simplified - would use grep/AST to find patterns
        return matches

    def _combine_patterns(
        self,
        structural: dict[str, Any],
        semantic: dict[str, Any],
    ) -> dict[str, Any]:
        """Combine structural and semantic pattern results."""
        combined = {}
        
        # Merge patterns from both sources
        all_pattern_types = set(structural.keys()) | set(semantic.keys())
        
        for pattern_type in all_pattern_types:
            combined[pattern_type] = {
                "structural": structural.get(pattern_type, []),
                "semantic": semantic.get(pattern_type, []),
            }
        
        return combined


