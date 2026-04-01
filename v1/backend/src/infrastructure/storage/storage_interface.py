"""Storage interface."""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import BinaryIO


class IStorage(ABC):
    """Storage interface for local and cloud storage."""

    @abstractmethod
    async def save(self, path: str, content: bytes | str) -> str:
        """Save content to storage and return storage path."""
        ...

    @abstractmethod
    async def read(self, path: str) -> bytes:
        """Read content from storage."""
        ...

    @abstractmethod
    async def exists(self, path: str) -> bool:
        """Check if path exists in storage."""
        ...

    @abstractmethod
    async def delete(self, path: str) -> bool:
        """Delete path from storage."""
        ...

    @abstractmethod
    async def get_url(self, path: str) -> str:
        """Get public URL for path (if applicable)."""
        ...


