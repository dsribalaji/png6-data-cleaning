"""S3 / MinIO storage adapter using boto3 (Backend.md)."""

from __future__ import annotations

import asyncio
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from planner.core.errors import AppError


class S3StorageAdapter:
    """StoragePort implementation backed by AWS S3 or MinIO via boto3."""

    def __init__(
        self,
        endpoint_url: str,
        bucket: str,
        access_key: str = "",
        secret_key: str = "",
        region: str = "us-east-1",
    ) -> None:
        self.endpoint_url = endpoint_url
        self.bucket = bucket
        self.access_key = access_key
        self.secret_key = secret_key
        self.region = region

        self._client: Any = boto3.client(
            "s3",
            endpoint_url=self.endpoint_url or None,
            aws_access_key_id=self.access_key or None,
            aws_secret_access_key=self.secret_key or None,
            region_name=self.region,
            config=Config(signature_version="s3v4"),
        )

    async def put(
        self, key: str, data: bytes, content_type: str = "application/octet-stream"
    ) -> None:
        """Upload bytes to S3/MinIO."""
        clean_key = key.lstrip("/")

        def _sync_put() -> None:
            self._client.put_object(
                Bucket=self.bucket,
                Key=clean_key,
                Body=data,
                ContentType=content_type,
            )

        await asyncio.to_thread(_sync_put)

    async def get(self, key: str) -> bytes:
        """Download bytes from S3/MinIO; raises AppError('NOT_FOUND') if missing."""
        clean_key = key.lstrip("/")

        def _sync_get() -> bytes:
            try:
                response = self._client.get_object(Bucket=self.bucket, Key=clean_key)
                return response["Body"].read()
            except ClientError as exc:
                code = exc.response.get("Error", {}).get("Code", "")
                if code in ("404", "NoSuchKey", "NotFound"):
                    raise AppError("NOT_FOUND", f"Object not found: {key}") from exc
                raise
            except Exception as exc:
                if "NoSuchKey" in str(exc) or "NotFound" in str(exc):
                    raise AppError("NOT_FOUND", f"Object not found: {key}") from exc
                raise

        return await asyncio.to_thread(_sync_get)

    async def presigned_get_url(self, key: str, expires_seconds: int = 900) -> str:
        """Generate a pre-signed download URL."""
        clean_key = key.lstrip("/")

        def _sync_presign() -> str:
            return self._client.generate_presigned_url(
                ClientMethod="get_object",
                Params={"Bucket": self.bucket, "Key": clean_key},
                ExpiresIn=expires_seconds,
            )

        return await asyncio.to_thread(_sync_presign)

    async def delete(self, key: str) -> None:
        """Delete an object from S3/MinIO."""
        clean_key = key.lstrip("/")

        def _sync_delete() -> None:
            self._client.delete_object(Bucket=self.bucket, Key=clean_key)

        await asyncio.to_thread(_sync_delete)

    async def exists(self, key: str) -> bool:
        """Check if an object exists in S3/MinIO."""
        clean_key = key.lstrip("/")

        def _sync_exists() -> bool:
            try:
                self._client.head_object(Bucket=self.bucket, Key=clean_key)
                return True
            except ClientError:
                return False

        return await asyncio.to_thread(_sync_exists)

    async def list(self, prefix: str) -> list[str]:
        """List all object keys with the given prefix."""
        clean_prefix = prefix.lstrip("/")

        def _sync_list() -> list[str]:
            keys: list[str] = []
            paginator = self._client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=self.bucket, Prefix=clean_prefix):
                for item in page.get("Contents", []):
                    keys.append(item["Key"])
            return keys

        return await asyncio.to_thread(_sync_list)

    # Aliases
    put_object = put
    get_object = get
