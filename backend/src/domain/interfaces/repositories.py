"""Repository interfaces."""
from abc import ABC, abstractmethod
from typing import Generic, TypeVar, Any
from domain.entities.user import User
from domain.entities.repository import Repository
from domain.entities.analysis import Analysis
from domain.entities.analysis_event import AnalysisEvent
from domain.entities.architecture_rule import ArchitectureRule, RepositoryArchitectureConfig
from domain.entities.user_profile import UserProfile

T = TypeVar("T")
ID = TypeVar("ID")


class IRepository(ABC, Generic[T, ID]):
    """Base repository interface."""

    @abstractmethod
    async def get_by_id(self, id: ID) -> T | None:
        ...

    @abstractmethod
    async def get_all(self, limit: int = 100, offset: int = 0) -> list[T]:
        ...

    @abstractmethod
    async def add(self, entity: T) -> T:
        ...

    @abstractmethod
    async def update(self, entity: T) -> T:
        ...

    @abstractmethod
    async def delete(self, id: ID) -> bool:
        ...


class IUserRepository(IRepository[User, str]):
    """Interface for user repository."""
    ...


class IRepositoryRepository(IRepository[Repository, str]):
    """Interface for repository repository."""
    
    @abstractmethod
    async def get_by_full_name(self, user_id: str, owner: str, name: str) -> Repository | None:
        ...
        
    @abstractmethod
    async def get_by_user_id(self, user_id: str, limit: int = 100, offset: int = 0) -> list[Repository]:
        ...


class IAnalysisRepository(IRepository[Analysis, str]):
    """Interface for analysis repository."""
    ...


class IAnalysisEventRepository(IRepository[AnalysisEvent, str]):
    """Interface for analysis event repository."""
    
    @abstractmethod
    async def get_by_analysis_id(self, analysis_id: str) -> list[AnalysisEvent]:
        """Get events for a specific analysis."""
        ...


class IArchitectureRuleRepository(ABC):
    """Interface for architecture rule repository (reference architecture)."""
    
    @abstractmethod
    async def get_by_id(self, id: str) -> ArchitectureRule | None:
        """Get a rule by its ID."""
        ...
    
    @abstractmethod
    async def get_by_blueprint_id(self, blueprint_id: str) -> list[ArchitectureRule]:
        """Get all rules for a blueprint."""
        ...
    
    @abstractmethod
    async def get_by_blueprint_and_type(self, blueprint_id: str, rule_type: str) -> list[ArchitectureRule]:
        """Get rules for a blueprint filtered by type."""
        ...
    
    @abstractmethod
    async def get_by_rule_id(self, blueprint_id: str, rule_id: str) -> ArchitectureRule | None:
        """Get a specific rule by blueprint_id and rule_id."""
        ...
    
    @abstractmethod
    async def add(self, rule: ArchitectureRule) -> ArchitectureRule:
        """Add a new rule."""
        ...
    
    @abstractmethod
    async def update(self, rule: ArchitectureRule) -> ArchitectureRule:
        """Update an existing rule."""
        ...
    
    @abstractmethod
    async def delete(self, id: str) -> bool:
        """Delete a rule by ID."""
        ...
    
    @abstractmethod
    async def delete_by_blueprint_id(self, blueprint_id: str) -> int:
        """Delete all rules for a blueprint. Returns count deleted."""
        ...
    
    @abstractmethod
    async def list_blueprints(self) -> list[str]:
        """List all unique blueprint IDs."""
        ...


class IRepositoryArchitectureRepository(ABC):
    """Interface for repository architecture repository (learned architecture)."""
    
    @abstractmethod
    async def get_by_id(self, id: str) -> ArchitectureRule | None:
        """Get a rule by its ID."""
        ...
    
    @abstractmethod
    async def get_by_repository_id(self, repository_id: str) -> list[ArchitectureRule]:
        """Get all learned rules for a repository."""
        ...
    
    @abstractmethod
    async def get_by_repository_and_type(self, repository_id: str, rule_type: str) -> list[ArchitectureRule]:
        """Get learned rules for a repository filtered by type."""
        ...
    
    @abstractmethod
    async def get_by_analysis_id(self, analysis_id: str) -> list[ArchitectureRule]:
        """Get all rules extracted in a specific analysis."""
        ...
    
    @abstractmethod
    async def add(self, rule: ArchitectureRule) -> ArchitectureRule:
        """Add a new learned rule."""
        ...
    
    @abstractmethod
    async def add_many(self, rules: list[ArchitectureRule]) -> list[ArchitectureRule]:
        """Add multiple learned rules."""
        ...
    
    @abstractmethod
    async def update(self, rule: ArchitectureRule) -> ArchitectureRule:
        """Update an existing rule."""
        ...
    
    @abstractmethod
    async def delete(self, id: str) -> bool:
        """Delete a rule by ID."""
        ...
    
    @abstractmethod
    async def delete_by_repository_id(self, repository_id: str) -> int:
        """Delete all rules for a repository. Returns count deleted."""
        ...


class IRepositoryArchitectureConfigRepository(ABC):
    """Interface for repository architecture config repository."""
    
    @abstractmethod
    async def get_by_repository_id(self, repository_id: str) -> RepositoryArchitectureConfig | None:
        """Get config for a repository."""
        ...
    
    @abstractmethod
    async def add(self, config: RepositoryArchitectureConfig) -> RepositoryArchitectureConfig:
        """Add a new config."""
        ...
    
    @abstractmethod
    async def update(self, config: RepositoryArchitectureConfig) -> RepositoryArchitectureConfig:
        """Update an existing config."""
        ...
    
    @abstractmethod
    async def upsert(self, config: RepositoryArchitectureConfig) -> RepositoryArchitectureConfig:
        """Insert or update a config."""
        ...
    
    @abstractmethod
    async def delete(self, repository_id: str) -> bool:
        """Delete config for a repository."""
        ...


class IUserProfileRepository(ABC):
    """Interface for user profile repository.

    Single-row design for now. When multi-user support is added,
    methods will accept a ``user_id`` parameter.
    """

    @abstractmethod
    async def get_default(self) -> UserProfile | None:
        """Get the default (single) user profile."""
        ...

    @abstractmethod
    async def upsert(self, profile: UserProfile) -> UserProfile:
        """Insert or update a user profile."""
        ...

    @abstractmethod
    async def set_active_repo(self, repo_id: str | None) -> None:
        """Set (or clear) the active repository."""
        ...
