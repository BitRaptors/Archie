"""Architecture rule domain entities."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Self
import uuid


@dataclass
class ArchitectureRule:
    """Represents an architecture rule (either reference or learned).
    
    Rules are observation-based and don't assume predefined patterns.
    Rule types for learned architecture:
    - 'purpose': What a file/module does (factual description)
    - 'dependency': Import relationships (what imports what)
    - 'convention': Observed naming/structural patterns
    - 'boundary': Observed separation between components
    
    Rule types for reference architecture:
    - 'layer': Layer definitions and dependencies
    - 'pattern': Design patterns
    - 'principle': Architectural principles
    - 'anti_pattern': Things to avoid
    - 'location': File location conventions
    """
    
    id: str
    rule_type: str
    rule_id: str
    name: str
    description: str | None
    rule_data: dict[str, Any]
    examples: dict[str, Any] | None = None
    confidence: float = 1.0
    source_files: list[str] | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    
    # For reference rules
    blueprint_id: str | None = None
    
    # For learned rules
    repository_id: str | None = None
    analysis_id: str | None = None

    @classmethod
    def create_reference_rule(
        cls,
        blueprint_id: str,
        rule_type: str,
        rule_id: str,
        name: str,
        rule_data: dict[str, Any],
        description: str | None = None,
        examples: dict[str, Any] | None = None,
    ) -> Self:
        """Factory method for creating a reference architecture rule."""
        now = datetime.now(timezone.utc)
        return cls(
            id=str(uuid.uuid4()),
            blueprint_id=blueprint_id,
            rule_type=rule_type,
            rule_id=rule_id,
            name=name,
            description=description,
            rule_data=rule_data,
            examples=examples,
            confidence=1.0,
            created_at=now,
        )
    
    @classmethod
    def create_learned_rule(
        cls,
        repository_id: str,
        rule_type: str,
        rule_id: str,
        name: str,
        rule_data: dict[str, Any],
        description: str | None = None,
        confidence: float = 1.0,
        source_files: list[str] | None = None,
        analysis_id: str | None = None,
    ) -> Self:
        """Factory method for creating a learned architecture rule from observation."""
        now = datetime.now(timezone.utc)
        return cls(
            id=str(uuid.uuid4()),
            repository_id=repository_id,
            analysis_id=analysis_id,
            rule_type=rule_type,
            rule_id=rule_id,
            name=name,
            description=description,
            rule_data=rule_data,
            confidence=confidence,
            source_files=source_files,
            created_at=now,
        )
    
    def is_reference_rule(self) -> bool:
        """Check if this is a reference architecture rule."""
        return self.blueprint_id is not None
    
    def is_learned_rule(self) -> bool:
        """Check if this is a learned architecture rule."""
        return self.repository_id is not None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert rule to dictionary for serialization."""
        result = {
            "id": self.id,
            "rule_type": self.rule_type,
            "rule_id": self.rule_id,
            "name": self.name,
            "description": self.description,
            "rule_data": self.rule_data,
            "confidence": self.confidence,
        }
        
        if self.blueprint_id:
            result["blueprint_id"] = self.blueprint_id
        if self.repository_id:
            result["repository_id"] = self.repository_id
        if self.analysis_id:
            result["analysis_id"] = self.analysis_id
        if self.examples:
            result["examples"] = self.examples
        if self.source_files:
            result["source_files"] = self.source_files
        if self.created_at:
            result["created_at"] = self.created_at.isoformat()
        if self.updated_at:
            result["updated_at"] = self.updated_at.isoformat()
            
        return result


@dataclass
class RepositoryArchitectureConfig:
    """Configuration for how architecture rules are resolved for a repository."""
    
    id: str
    repository_id: str
    reference_blueprint_id: str | None
    use_learned_architecture: bool
    merge_strategy: str  # 'learned_primary', 'reference_primary', 'learned_only', 'reference_only'
    created_at: datetime | None = None
    updated_at: datetime | None = None
    
    VALID_STRATEGIES = ['learned_primary', 'reference_primary', 'learned_only', 'reference_only']
    
    @classmethod
    def create(
        cls,
        repository_id: str,
        reference_blueprint_id: str | None = None,
        use_learned_architecture: bool = True,
        merge_strategy: str = 'learned_primary',
    ) -> Self:
        """Factory method for creating a new config with defaults."""
        if merge_strategy not in cls.VALID_STRATEGIES:
            raise ValueError(f"Invalid merge strategy: {merge_strategy}. Must be one of {cls.VALID_STRATEGIES}")
        
        now = datetime.now(timezone.utc)
        return cls(
            id=str(uuid.uuid4()),
            repository_id=repository_id,
            reference_blueprint_id=reference_blueprint_id,
            use_learned_architecture=use_learned_architecture,
            merge_strategy=merge_strategy,
            created_at=now,
        )
    
    def update_strategy(self, merge_strategy: str) -> None:
        """Update the merge strategy."""
        if merge_strategy not in self.VALID_STRATEGIES:
            raise ValueError(f"Invalid merge strategy: {merge_strategy}. Must be one of {self.VALID_STRATEGIES}")
        self.merge_strategy = merge_strategy
        self.updated_at = datetime.now(timezone.utc)
    
    def set_reference_blueprint(self, blueprint_id: str | None) -> None:
        """Set or clear the reference blueprint."""
        self.reference_blueprint_id = blueprint_id
        self.updated_at = datetime.now(timezone.utc)
