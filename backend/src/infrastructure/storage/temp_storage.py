"""Temporary storage for repository clones."""
import tempfile
from pathlib import Path
from typing import BinaryIO
from infrastructure.storage.storage_interface import IStorage
from config.settings import get_settings


class TempStorage(IStorage):
    """Temporary storage implementation for ephemeral container storage."""

    def __init__(self, base_path: Path | None = None):
        """Initialize temporary storage."""
        if base_path:
            self._base_path = base_path
        else:
            settings = get_settings()
            self._base_path = Path(settings.temp_storage_path)
        self._base_path.mkdir(parents=True, exist_ok=True)

    async def save(self, path: str, content: bytes | str) -> str:
        """Save content to temporary storage."""
        full_path = self._base_path / path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        
        if isinstance(content, str):
            full_path.write_text(content, encoding="utf-8")
        else:
            full_path.write_bytes(content)
        
        return str(full_path.relative_to(self._base_path))

    async def read(self, path: str) -> bytes:
        """Read content from temporary storage."""
        full_path = self._base_path / path
        if not full_path.exists():
            raise FileNotFoundError(f"Path not found: {path}")
        return full_path.read_bytes()

    async def exists(self, path: str) -> bool:
        """Check if path exists."""
        full_path = self._base_path / path
        return full_path.exists()

    async def delete(self, path: str) -> bool:
        """Delete path from temporary storage."""
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
        """Get local file path."""
        return str(self._base_path / path)

    def get_base_path(self) -> Path:
        """Get base path for temporary storage."""
        return self._base_path
