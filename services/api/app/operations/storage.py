"""Object storage (MinIO hosted with the stack, S3 protocol): files are named by the server, never by a client.

Configuration: S3_ENDPOINT, S3_ACCESS_KEY, S3_SECRET_KEY; one bucket (`aylal`). Presigned URLs are computed locally
(no network call) and last at most 15 minutes.
"""
import asyncio
import os
from typing import Any

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

BUCKET = "aylal"
MAX_PRESIGN_SECONDS = 900


class ObjectStorage:
    def __init__(self, endpoint: str, access_key: str, secret_key: str, bucket: str = BUCKET) -> None:
        self.bucket = bucket
        self._client: Any = boto3.client(
            "s3", endpoint_url=endpoint, aws_access_key_id=access_key, aws_secret_access_key=secret_key,
            region_name="us-east-1", config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        )

    async def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        await asyncio.to_thread(self._client.put_object, Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)

    async def get(self, key: str) -> bytes:
        def read() -> bytes:
            body: bytes = self._client.get_object(Bucket=self.bucket, Key=key)["Body"].read()
            return body

        return await asyncio.to_thread(read)

    async def exists(self, key: str) -> bool:
        def head() -> bool:
            try:
                self._client.head_object(Bucket=self.bucket, Key=key)
            except ClientError as e:
                if e.response.get("Error", {}).get("Code") in ("404", "NoSuchKey", "NotFound"):
                    return False
                raise
            return True

        return await asyncio.to_thread(head)

    def presign_get(self, key: str, expires_seconds: int = MAX_PRESIGN_SECONDS) -> str:
        seconds = max(1, min(int(expires_seconds), MAX_PRESIGN_SECONDS))
        url: str = self._client.generate_presigned_url(
            "get_object", Params={"Bucket": self.bucket, "Key": key}, ExpiresIn=seconds
        )
        return url


def get_storage() -> ObjectStorage:
    env = os.environ
    return ObjectStorage(env.get("S3_ENDPOINT", ""), env.get("S3_ACCESS_KEY", ""), env.get("S3_SECRET_KEY", ""))
