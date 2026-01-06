"""Local file system storage implementation."""
from pathlib import Path
from typing import BinaryIO
from infrastructure.storage.storage_interface import IStorage
from config.settings import get_settings


class LocalStorage(IStorage):
    """Local file system storage implementation."""

    def __init__(self, base_path: str | None = None):
        """Initialize local storage."""
        settings = get_settings()
        self._base_path = Path(base_path or settings.storage_path)
        self._base_path.mkdir(parents=True, exist_ok=True)

    async def save(self, path: str, content: bytes | str) -> str:
        """Save content to local file system."""
        full_path = self._base_path / path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        
        if isinstance(content, str):
            full_path.write_text(content, encoding="utf-8")
        else:
            full_path.write_bytes(content)
        
        return str(full_path.relative_to(self._base_path))

    async def read(self, path: str) -> bytes:
        """Read content from local file system."""
        full_path = self._base_path / path
        if not full_path.exists():
            raise FileNotFoundError(f"Path not found: {path}")
        return full_path.read_bytes()

    async def exists(self, path: str) -> bool:
        """Check if path exists."""
        full_path = self._base_path / path
        return full_path.exists()

    async def delete(self, path: str) -> bool:
        """Delete path from local file system."""
        full_path = self._base_path / path
        if full_path.exists():
            if full_path.is_file():
                full_path.unlink()
            else:
                import shutil
                shutil.rmtree(full_path)
            return True
        return False

    async def get_url(self, path: str) -> str:
        """Get local file path (not a URL for local storage)."""
        return str(self._base_path / path)

