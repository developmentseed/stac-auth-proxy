"""Asset signer for S3 assets."""

import logging
import re
from dataclasses import dataclass
from typing import Literal

import boto3
from botocore.exceptions import ClientError
from fastapi import HTTPException


@dataclass
class S3AssetSigner:
    """Asset signer for S3 assets."""

    bucket_pattern: str = r".*"
    max_expiration: int = 3600

    def endpoint(
        self, payload: "S3AssetSignerPayload", expiration: int = 3600
    ) -> dict[Literal["signed_url"], str]:
        """Generate a presigned URL to share an S3 object."""
        if not re.match(self.bucket_pattern, payload.bucket_name):
            return HTTPException(status_code=404, detail="Item not found")

        try:
            url = boto3.client("s3").generate_presigned_url(
                "get_object",
                Params={"Bucket": payload.bucket_name, "Key": payload.object_name},
                ExpiresIn=min(expiration, self.max_expiration),
            )
            return {"signed_url": url}
        except ClientError as e:
            logging.error(e)
            return HTTPException(status_code=500, detail="Internal server error")


@dataclass
class S3AssetSignerPayload:
    """Signs S3 assets."""

    bucket_name: str
    object_name: str
