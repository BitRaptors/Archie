"""Resolved architecture domain entity."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Self

from domain.entities.architecture_rule import ArchitectureRule, RepositoryArchitectureConfig


@dataclass
class ResolvedArchitecture:
    """Represents the merged architecture rules for a repository.
    
    This combines reference architecture (if configured) with learned architecture
    according to the configured merge strategy.
    """
    
    repository_id: str
    config: RepositoryArchitectureConfig | None
    rules: list[ArchitectureRule] = field(default_factory=list)
    reference_rules_count: int = 0
    learned_rules_count: int = 0
    resolved_at: datetime | None = None
    
    @classmethod
    def create(
        cls,
        repository_id: str,
        config: RepositoryArchitectureConfig | None,
        rules: list[ArchitectureRule],
    ) -> Self:
        """Factory method for creating a resolved architecture."""
        reference_count = sum(1 for r in rules if r.is_reference_rule())
        learned_count = sum(1 for r in rules if r.is_learned_rule())
        
        return cls(
            repository_id=repository_id,
            config=config,
            rules=rules,
            reference_rules_count=reference_count,
            learned_rules_count=learned_count,
            resolved_at=datetime.now(timezone.utc),
        )
    
    def get_rules_by_type(self, rule_type: str) -> list[ArchitectureRule]:
        """Get all rules of a specific type."""
        return [r for r in self.rules if r.rule_type == rule_type]
    
    def get_purpose_rules(self) -> list[ArchitectureRule]:
        """Get all purpose rules (what files/modules do)."""
        return self.get_rules_by_type("purpose")
    
    def get_dependency_rules(self) -> list[ArchitectureRule]:
        """Get all dependency rules (import relationships)."""
        return self.get_rules_by_type("dependency")
    
    def get_convention_rules(self) -> list[ArchitectureRule]:
        """Get all convention rules (naming/structural patterns)."""
        return self.get_rules_by_type("convention")
    
    def get_boundary_rules(self) -> list[ArchitectureRule]:
        """Get all boundary rules (component separation)."""
        return self.get_rules_by_type("boundary")
    
    def get_layer_rules(self) -> list[ArchitectureRule]:
        """Get all layer rules (from reference architecture)."""
        return self.get_rules_by_type("layer")
    
    def get_pattern_rules(self) -> list[ArchitectureRule]:
        """Get all pattern rules (from reference architecture)."""
        return self.get_rules_by_type("pattern")
    
    def get_rule_by_id(self, rule_id: str) -> ArchitectureRule | None:
        """Get a specific rule by its rule_id."""
        for rule in self.rules:
            if rule.rule_id == rule_id:
                return rule
        return None
    
    def get_rules_for_file(self, file_path: str) -> list[ArchitectureRule]:
        """Get all rules that apply to a specific file."""
        relevant_rules = []
        for rule in self.rules:
            # Check if file is in source_files
            if rule.source_files and file_path in rule.source_files:
                relevant_rules.append(rule)
                continue
            
            # Check if rule_data references this file
            rule_data = rule.rule_data
            if isinstance(rule_data, dict):
                # Check common patterns for file references
                if rule_data.get("file") == file_path:
                    relevant_rules.append(rule)
                elif rule_data.get("path") == file_path:
                    relevant_rules.append(rule)
                elif file_path in rule_data.get("files", []):
                    relevant_rules.append(rule)
                elif file_path in rule_data.get("imports", []):
                    relevant_rules.append(rule)
                elif file_path in rule_data.get("imported_by", []):
                    relevant_rules.append(rule)
        
        return relevant_rules
    
    def get_merge_strategy(self) -> str:
        """Get the merge strategy used."""
        if self.config:
            return self.config.merge_strategy
        return "learned_only"  # Default if no config
    
    def has_reference_architecture(self) -> bool:
        """Check if reference architecture is included."""
        return self.reference_rules_count > 0
    
    def has_learned_architecture(self) -> bool:
        """Check if learned architecture is included."""
        return self.learned_rules_count > 0
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "repository_id": self.repository_id,
            "merge_strategy": self.get_merge_strategy(),
            "reference_rules_count": self.reference_rules_count,
            "learned_rules_count": self.learned_rules_count,
            "total_rules_count": len(self.rules),
            "rules": [r.to_dict() for r in self.rules],
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }
    
    def to_summary_dict(self) -> dict[str, Any]:
        """Convert to summary dictionary (without full rules)."""
        rules_by_type: dict[str, int] = {}
        for rule in self.rules:
            rules_by_type[rule.rule_type] = rules_by_type.get(rule.rule_type, 0) + 1
        
        return {
            "repository_id": self.repository_id,
            "merge_strategy": self.get_merge_strategy(),
            "reference_rules_count": self.reference_rules_count,
            "learned_rules_count": self.learned_rules_count,
            "total_rules_count": len(self.rules),
            "rules_by_type": rules_by_type,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
        }
