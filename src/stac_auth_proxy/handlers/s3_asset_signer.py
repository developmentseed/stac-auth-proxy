import logging
import re
from dataclasses import dataclass

import boto3
from botocore.exceptions import ClientError
from fastapi import HTTPException


@dataclass
class S3AssetSigner:
    bucket_pattern: str = r".*"

    def endpoint(self, payload: "S3AssetSignerPayload", expiration: int = 3600) -> str:
        """Generate a presigned URL to share an S3 object."""
        if not re.match(self.bucket_pattern, payload.bucket_name):
            return HTTPException(status_code=404, detail="Item not found")

        try:
            return boto3.client("s3").generate_presigned_url(
                "get_object",
                Params={"Bucket": payload.bucket_name, "Key": payload.object_name},
                ExpiresIn=expiration,
            )
        except ClientError as e:
            logging.error(e)
            return HTTPException(status_code=500, detail="Internal server error")


@dataclass
class S3AssetSignerPayload:
    """Signs S3 assets."""

    bucket_name: str
    object_name: str
