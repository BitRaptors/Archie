"""Architecture resolver service for merging reference and learned architectures."""
import logging
from typing import Any

from domain.entities.architecture_rule import ArchitectureRule, RepositoryArchitectureConfig
from domain.entities.resolved_architecture import ResolvedArchitecture
from domain.interfaces.repositories import (
    IArchitectureRuleRepository,
    IRepositoryArchitectureConfigRepository,
    IRepositoryArchitectureRepository,
)

logger = logging.getLogger(__name__)


class ArchitectureResolver:
    """Resolves architecture rules from multiple sources.
    
    This service merges reference architecture (from templates) with
    learned architecture (from analysis) according to user configuration.
    
    Merge strategies:
    - learned_primary (default): Learned rules take precedence, reference fills gaps
    - reference_primary: Reference rules take precedence, learned adds extras
    - learned_only: Only learned architecture, ignore reference
    - reference_only: Only reference architecture, ignore learned
    """
    
    def __init__(
        self,
        architecture_rule_repo: IArchitectureRuleRepository,
        repository_architecture_repo: IRepositoryArchitectureRepository,
        config_repo: IRepositoryArchitectureConfigRepository,
    ):
        """Initialize resolver.
        
        Args:
            architecture_rule_repo: Repository for reference architecture rules
            repository_architecture_repo: Repository for learned architecture rules
            config_repo: Repository for architecture configuration
        """
        self._architecture_rule_repo = architecture_rule_repo
        self._repository_architecture_repo = repository_architecture_repo
        self._config_repo = config_repo
    
    async def get_rules_for_repository(
        self,
        repository_id: str,
    ) -> ResolvedArchitecture:
        """Get merged architecture rules for a repository.
        
        Args:
            repository_id: ID of the repository
            
        Returns:
            ResolvedArchitecture with merged rules
        """
        # Get repository configuration
        config = await self._config_repo.get_by_repository_id(repository_id)
        
        # Determine which sources to load
        reference_rules: list[ArchitectureRule] = []
        learned_rules: list[ArchitectureRule] = []
        
        if config:
            strategy = config.merge_strategy
            
            # Load reference rules if needed
            if strategy in ["learned_primary", "reference_primary", "reference_only"]:
                if config.reference_blueprint_id:
                    reference_rules = await self._architecture_rule_repo.get_by_blueprint_id(
                        config.reference_blueprint_id
                    )
            
            # Load learned rules if needed
            if strategy in ["learned_primary", "reference_primary", "learned_only"]:
                if config.use_learned_architecture:
                    learned_rules = await self._repository_architecture_repo.get_by_repository_id(
                        repository_id
                    )
        else:
            # Default: learned_primary with all available rules
            learned_rules = await self._repository_architecture_repo.get_by_repository_id(
                repository_id
            )
        
        # Merge rules according to strategy
        merged_rules = self._merge_rules(
            reference_rules,
            learned_rules,
            config.merge_strategy if config else "learned_primary",
        )
        
        return ResolvedArchitecture.create(
            repository_id=repository_id,
            config=config,
            rules=merged_rules,
        )
    
    async def get_rules_by_type(
        self,
        repository_id: str,
        rule_type: str,
    ) -> list[ArchitectureRule]:
        """Get rules of a specific type for a repository.
        
        Args:
            repository_id: Repository ID
            rule_type: Type of rules to get
            
        Returns:
            List of rules matching the type
        """
        resolved = await self.get_rules_for_repository(repository_id)
        return resolved.get_rules_by_type(rule_type)
    
    async def get_layer_rules(
        self,
        repository_id: str,
    ) -> list[ArchitectureRule]:
        """Get layer rules for a repository.
        
        Args:
            repository_id: Repository ID
            
        Returns:
            List of layer rules
        """
        return await self.get_rules_by_type(repository_id, "layer")
    
    async def get_dependency_rules(
        self,
        repository_id: str,
    ) -> list[ArchitectureRule]:
        """Get dependency rules for a repository.
        
        Args:
            repository_id: Repository ID
            
        Returns:
            List of dependency rules
        """
        return await self.get_rules_by_type(repository_id, "dependency")
    
    async def configure_repository(
        self,
        repository_id: str,
        reference_blueprint_id: str | None = None,
        use_learned_architecture: bool = True,
        merge_strategy: str = "learned_primary",
    ) -> RepositoryArchitectureConfig:
        """Configure architecture sources for a repository.
        
        Args:
            repository_id: Repository ID
            reference_blueprint_id: Blueprint to use as reference
            use_learned_architecture: Whether to use learned rules
            merge_strategy: How to merge rules
            
        Returns:
            Updated configuration
        """
        config = RepositoryArchitectureConfig.create(
            repository_id=repository_id,
            reference_blueprint_id=reference_blueprint_id,
            use_learned_architecture=use_learned_architecture,
            merge_strategy=merge_strategy,
        )
        
        return await self._config_repo.upsert(config)
    
    def _merge_rules(
        self,
        reference: list[ArchitectureRule],
        learned: list[ArchitectureRule],
        strategy: str,
    ) -> list[ArchitectureRule]:
        """Merge rules based on strategy.
        
        Args:
            reference: Reference architecture rules
            learned: Learned architecture rules
            strategy: Merge strategy
            
        Returns:
            Merged list of rules
        """
        if strategy == "learned_only":
            return learned
        
        if strategy == "reference_only":
            return reference
        
        if strategy == "learned_primary":
            # Learned takes precedence, reference fills gaps
            return self._merge_learned_primary(learned, reference)
        
        if strategy == "reference_primary":
            # Reference takes precedence, learned adds extras
            return self._merge_reference_primary(reference, learned)
        
        # Default to learned_primary
        return self._merge_learned_primary(learned, reference)
    
    def _merge_learned_primary(
        self,
        learned: list[ArchitectureRule],
        reference: list[ArchitectureRule],
    ) -> list[ArchitectureRule]:
        """Merge with learned rules taking precedence.
        
        Learned rules win conflicts, reference fills gaps.
        
        Args:
            learned: Learned rules (primary)
            reference: Reference rules (fallback)
            
        Returns:
            Merged rules
        """
        merged = list(learned)  # Start with all learned rules
        
        # Build set of rule identifiers from learned rules
        learned_keys = set()
        for rule in learned:
            # Key by type and normalized rule_id
            key = (rule.rule_type, self._normalize_rule_id(rule.rule_id))
            learned_keys.add(key)
            
            # Also key by type and similar patterns
            if rule.rule_data:
                if "file" in rule.rule_data:
                    learned_keys.add((rule.rule_type, rule.rule_data["file"]))
                if "path" in rule.rule_data:
                    learned_keys.add((rule.rule_type, rule.rule_data["path"]))
        
        # Add reference rules that don't conflict
        for rule in reference:
            key = (rule.rule_type, self._normalize_rule_id(rule.rule_id))
            
            # Check if this rule conflicts with learned
            if key not in learned_keys:
                # Also check rule_data patterns
                has_conflict = False
                if rule.rule_data:
                    if "file" in rule.rule_data:
                        if (rule.rule_type, rule.rule_data["file"]) in learned_keys:
                            has_conflict = True
                    if "path" in rule.rule_data:
                        if (rule.rule_type, rule.rule_data["path"]) in learned_keys:
                            has_conflict = True
                
                if not has_conflict:
                    merged.append(rule)
        
        return merged
    
    def _merge_reference_primary(
        self,
        reference: list[ArchitectureRule],
        learned: list[ArchitectureRule],
    ) -> list[ArchitectureRule]:
        """Merge with reference rules taking precedence.
        
        Reference rules win conflicts, learned adds extras.
        
        Args:
            reference: Reference rules (primary)
            learned: Learned rules (additions)
            
        Returns:
            Merged rules
        """
        merged = list(reference)  # Start with all reference rules
        
        # Build set of rule identifiers from reference rules
        reference_keys = set()
        for rule in reference:
            key = (rule.rule_type, self._normalize_rule_id(rule.rule_id))
            reference_keys.add(key)
            
            if rule.rule_data:
                if "file" in rule.rule_data:
                    reference_keys.add((rule.rule_type, rule.rule_data["file"]))
                if "path" in rule.rule_data:
                    reference_keys.add((rule.rule_type, rule.rule_data["path"]))
        
        # Add learned rules that don't conflict
        for rule in learned:
            key = (rule.rule_type, self._normalize_rule_id(rule.rule_id))
            
            if key not in reference_keys:
                has_conflict = False
                if rule.rule_data:
                    if "file" in rule.rule_data:
                        if (rule.rule_type, rule.rule_data["file"]) in reference_keys:
                            has_conflict = True
                    if "path" in rule.rule_data:
                        if (rule.rule_type, rule.rule_data["path"]) in reference_keys:
                            has_conflict = True
                
                if not has_conflict:
                    merged.append(rule)
        
        return merged
    
    def _normalize_rule_id(self, rule_id: str) -> str:
        """Normalize a rule ID for comparison.
        
        Args:
            rule_id: Original rule ID
            
        Returns:
            Normalized rule ID
        """
        # Remove common prefixes and normalize
        prefixes = ["layer-", "pattern-", "principle-", "location-", "anti-pattern-",
                   "purpose-", "dependency-", "convention-", "boundary-",
                   "dep-", "conv-"]
        
        normalized = rule_id.lower()
        for prefix in prefixes:
            if normalized.startswith(prefix):
                normalized = normalized[len(prefix):]
                break
        
        return normalized
