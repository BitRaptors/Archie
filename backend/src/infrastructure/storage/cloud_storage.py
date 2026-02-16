"""Cloud storage implementations."""
from typing import BinaryIO
from infrastructure.storage.storage_interface import IStorage
from config.settings import get_settings


class GCSStorage(IStorage):
    """Google Cloud Storage implementation."""

    def __init__(self, bucket_name: str | None = None):
        """Initialize GCS storage."""
        from google.cloud import storage
        settings = get_settings()
        self._bucket_name = bucket_name or settings.gcs_bucket_name
        self._client = storage.Client()
        self._bucket = self._client.bucket(self._bucket_name)

    async def save(self, path: str, content: bytes | str) -> str:
        """Save content to GCS."""
        blob = self._bucket.blob(path)
        if isinstance(content, str):
            blob.upload_from_string(content, content_type="text/plain")
        else:
            blob.upload_from_string(content)
        return path

    async def read(self, path: str) -> bytes:
        """Read content from GCS."""
        blob = self._bucket.blob(path)
        return blob.download_as_bytes()

    async def exists(self, path: str) -> bool:
        """Check if path exists."""
        blob = self._bucket.blob(path)
        return blob.exists()

    async def delete(self, path: str) -> bool:
        """Delete path from GCS."""
        blob = self._bucket.blob(path)
        blob.delete()
        return True

    async def get_url(self, path: str) -> str:
        """Get public URL."""
        blob = self._bucket.blob(path)
        return blob.public_url


class S3Storage(IStorage):
    """AWS S3 storage implementation."""

    def __init__(self, bucket_name: str | None = None):
        """Initialize S3 storage."""
        import boto3
        settings = get_settings()
        self._bucket_name = bucket_name or settings.s3_bucket_name
        self._client = boto3.client(
            "s3",
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            region_name=settings.aws_region,
        )

    async def save(self, path: str, content: bytes | str) -> str:
        """Save content to S3."""
        if isinstance(content, str):
            content_bytes = content.encode("utf-8")
            content_type = "text/plain"
        else:
            content_bytes = content
            content_type = "application/octet-stream"
        
        self._client.put_object(
            Bucket=self._bucket_name,
            Key=path,
            Body=content_bytes,
            ContentType=content_type,
        )
        return path

    async def read(self, path: str) -> bytes:
        """Read content from S3."""
        response = self._client.get_object(Bucket=self._bucket_name, Key=path)
        return response["Body"].read()

    async def exists(self, path: str) -> bool:
        """Check if path exists."""
        try:
            self._client.head_object(Bucket=self._bucket_name, Key=path)
            return True
        except:
            return False

    async def delete(self, path: str) -> bool:
        """Delete path from S3."""
        self._client.delete_object(Bucket=self._bucket_name, Key=path)
        return True

    async def get_url(self, path: str) -> str:
        """Get public URL."""
        return f"https://{self._bucket_name}.s3.amazonaws.com/{path}"


class StorageFactory:
    """Factory for creating storage instances."""

    @staticmethod
    def create(storage_type: str | None = None) -> IStorage:
        """Create storage instance."""
        from config.settings import get_settings
        settings = get_settings()
        storage_type = storage_type or settings.storage_type
        
        if storage_type == "gcs":
            return GCSStorage()
        elif storage_type == "s3":
            return S3Storage()
        else:
            from infrastructure.storage.local_storage import LocalStorage
            return LocalStorage()


