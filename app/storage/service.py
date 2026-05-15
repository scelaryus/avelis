"""GFI Platform - Object Storage Service (S3/MinIO compatible)."""
import os
import structlog
import boto3
from botocore.exceptions import ClientError
from app.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()
_storage_service = None


class ObjectStorageService:
    """S3/MinIO compatible object storage service."""

    def __init__(self):
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT,
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
            region_name="us-east-1",
            use_ssl=settings.S3_USE_SSL,
        )
        self._ensure_buckets()

    def _ensure_buckets(self):
        """Create buckets if they don't exist."""
        for bucket in [settings.S3_BUCKET_DOCUMENTS, settings.S3_BUCKET_RENDERS, settings.S3_BUCKET_ARTIFACTS]:
            try:
                self.client.head_bucket(Bucket=bucket)
            except ClientError:
                try:
                    self.client.create_bucket(Bucket=bucket)
                    logger.info("bucket_created", bucket=bucket)
                except Exception as e:
                    logger.warning("bucket_create_failed", bucket=bucket, error=str(e))

    def _get_bucket(self, key: str) -> str:
        """Determine bucket from key prefix."""
        if key.startswith("renders/"):
            return settings.S3_BUCKET_RENDERS
        elif key.startswith("artifacts/"):
            return settings.S3_BUCKET_ARTIFACTS
        else:
            return settings.S3_BUCKET_DOCUMENTS

    async def upload(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        """Upload data to object storage."""
        bucket = self._get_bucket(key)
        self.client.put_object(
            Bucket=bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )
        logger.info("object_uploaded", bucket=bucket, key=key, size=len(data))
        return key

    async def download(self, key: str) -> bytes:
        """Download data from object storage."""
        bucket = self._get_bucket(key)
        try:
            response = self.client.get_object(Bucket=bucket, Key=key)
            return response["Body"].read()
        except ClientError as e:
            logger.error("object_download_failed", bucket=bucket, key=key, error=str(e))
            raise

    async def delete(self, key: str):
        """Delete object from storage."""
        bucket = self._get_bucket(key)
        self.client.delete_object(Bucket=bucket, Key=key)
        logger.info("object_deleted", bucket=bucket, key=key)

    async def get_presigned_url(self, key: str, expires_in: int = 3600) -> str:
        """Generate a presigned URL for an object."""
        bucket = self._get_bucket(key)
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expires_in,
        )

    async def exists(self, key: str) -> bool:
        """Check if an object exists."""
        bucket = self._get_bucket(key)
        try:
            self.client.head_object(Bucket=bucket, Key=key)
            return True
        except ClientError:
            return False


class LocalStorageService:
    """Local filesystem fallback for development without S3."""

    def __init__(self, base_dir: str = "./storage_data"):
        self.base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)

    async def upload(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        path = os.path.join(self.base_dir, key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
        return key

    async def download(self, key: str) -> bytes:
        path = os.path.join(self.base_dir, key)
        with open(path, "rb") as f:
            return f.read()

    async def delete(self, key: str):
        path = os.path.join(self.base_dir, key)
        if os.path.exists(path):
            os.remove(path)

    async def get_presigned_url(self, key: str, expires_in: int = 3600) -> str:
        return f"/storage/{key}"

    async def exists(self, key: str) -> bool:
        return os.path.exists(os.path.join(self.base_dir, key))


def get_storage_service():
    """Get storage service - use local if S3 not available."""
    global _storage_service
    if _storage_service is not None:
        return _storage_service

    try:
        _storage_service = ObjectStorageService()
    except Exception:
        logger.warning("s3_not_available, using local storage")
        _storage_service = LocalStorageService()
    return _storage_service
