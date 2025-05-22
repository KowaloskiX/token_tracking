from __future__ import annotations

# New helper module for AWS S3 file storage
# Provides an interface similar to the previous vercel_upload helper so that the rest
# of the codebase can switch from Vercel Blob to S3 with minimal changes.

import os
from urllib.parse import urlparse

from dotenv import load_dotenv
from fastapi import HTTPException

try:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError as e:  # pragma: no cover
    # Provide a clear error if boto3 is missing
    raise RuntimeError(
        "boto3 must be installed to use the S3 helper (pip install boto3)."
    ) from e

load_dotenv()

AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION", "eu-north-1")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")

if not all([AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, S3_BUCKET_NAME]):
    missing = [
        name
        for name, value in {
            "AWS_ACCESS_KEY_ID": AWS_ACCESS_KEY_ID,
            "AWS_SECRET_ACCESS_KEY": AWS_SECRET_ACCESS_KEY,
            "S3_BUCKET_NAME": S3_BUCKET_NAME,
        }.items()
        if not value
    ]
    raise RuntimeError(
        f"Missing required environment variables for S3 upload: {', '.join(missing)}"
    )

# Initialize the S3 client once at import time so we can reuse the connection.
s3_client = boto3.client(
    "s3",
    region_name=AWS_REGION,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
)


def _extract_key(key_or_url: str) -> str:
    """Return the S3 object key from a provided key or full https URL."""
    if key_or_url.startswith("http"):
        parsed = urlparse(key_or_url)
        # parsed.path starts with '/'; strip it off to get the key
        return parsed.path.lstrip("/")
    return key_or_url


# ---------------------------------------------------------------------------
# Public helper functions (mirroring previous vercel_upload API)
# ---------------------------------------------------------------------------

def upload_file_to_s3(filename: str, file_content: bytes) -> str:  # noqa: WPS110
    """Upload *file_content* to S3 under a *unique* key and return the public URL.

    To avoid collisions we prefix the original ``filename`` with a UTC timestamp
    down to milliseconds (e.g. ``20250519T141530123_myfile.pdf``).  The
    *original* filename is preserved for users by setting the
    ``Content-Disposition`` header so that when the browser downloads the file
    it suggests the original name, not the timestamp-prefixed key.
    """
    # Standard library import inside function to avoid global deps
    from datetime import datetime

    # Build a unique key: <YYYYmmddTHHMMSSfff>_filename
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%S%f")[:-3]  # milliseconds
    unique_key = f"{ts}_{filename}"

    try:
        s3_client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=unique_key,
            Body=file_content,
            # Preserve the original filename for download prompts
            ContentDisposition=f'attachment; filename="{filename}"',
            ACL='public-read'  # Make the object publicly readable
        )

        # The default public URL format. Adjust if you use a custom domain/CLOUDFRONT.
        return f"https://{S3_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{unique_key}"
    except (BotoCoreError, ClientError) as exc:  # pragma: no cover
        raise HTTPException(
            status_code=500,
            detail=f"Error uploading file to S3: {str(exc)}",
        ) from exc


def delete_file_from_s3(key_or_url: str) -> None:  # noqa: WPS110
    """Delete a single file from S3 given its *key_or_url*.

    Accepts either the raw object key (e.g. ``folder/file.pdf``) or the full
    ``https://bucket.s3.region.amazonaws.com/folder/file.pdf`` URL.
    """
    key = _extract_key(key_or_url)
    try:
        s3_client.delete_object(Bucket=S3_BUCKET_NAME, Key=key)
    except (BotoCoreError, ClientError) as exc:  # pragma: no cover
        raise HTTPException(
            status_code=500,
            detail=f"Error deleting file from S3: {str(exc)}",
        ) from exc


def delete_files_from_s3(keys_or_urls: list[str]) -> None:  # noqa: WPS110
    """Batch-delete multiple objects from S3.

    Accepts a list containing either raw keys or full URLs.
    """
    if not keys_or_urls:
        return

    objects = [{"Key": _extract_key(item)} for item in keys_or_urls]

    try:
        s3_client.delete_objects(Bucket=S3_BUCKET_NAME, Delete={"Objects": objects})
    except (BotoCoreError, ClientError) as exc:  # pragma: no cover
        raise HTTPException(
            status_code=500,
            detail=f"Error deleting files from S3: {str(exc)}",
        ) from exc 