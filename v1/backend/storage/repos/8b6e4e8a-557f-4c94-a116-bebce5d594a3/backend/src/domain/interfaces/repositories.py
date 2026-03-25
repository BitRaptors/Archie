"""Repository interfaces."""
from abc import ABC, abstractmethod
from typing import Generic, TypeVar, Any
from domain.entities.user import User
from domain.entities.repository import Repository
from domain.entities.analysis import Analysis
from domain.entities.analysis_event import AnalysisEvent
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
