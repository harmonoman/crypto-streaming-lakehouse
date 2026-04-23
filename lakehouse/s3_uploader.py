"""
lakehouse/s3_uploader.py

Optional S3 upload for exported Parquet files.

Upload is triggered ONLY when the S3_BUCKET environment variable is set.
If S3_BUCKET is absent, this module is a complete no-op — no boto3
import errors, no configuration required, no side effects.

Why optional?
    S3 upload is a "backup to cloud" step. The local Parquet file is
    always the source of truth. Cloud upload enhances durability and
    enables remote analytics tools, but must never become a point of
    pipeline failure.

Why swallow upload errors?
    A transient S3 error (network blip, credentials expiry, rate limit)
    should not roll back a successful local export. The data is safe on
    disk. The warning log makes the failure visible without crashing the
    pipeline.

Usage:
    from lakehouse.s3_uploader import upload_file_to_s3

    upload_file_to_s3(
        local_path="data/gold/gold_vwap_1min/year=2026/month=04/day=23/part-abc.parquet",
        base_path="data/gold",
    )
"""

import os

import boto3

from shared.logger import get_logger

logger = get_logger("lakehouse.s3_uploader")


def upload_file_to_s3(local_path: str, base_path: str) -> None:
    """
    Upload a local Parquet file to S3 if S3_BUCKET is configured.

    S3 key is derived by stripping base_path from local_path:
        data/gold/gold_vwap_1min/year=2026/.../file.parquet
        → gold_vwap_1min/year=2026/.../file.parquet

    Args:
        local_path: Absolute or relative path to the local Parquet file.
        base_path:  Prefix to strip when constructing the S3 key.
                    Typically the output_path / "gold" root.
    """
    bucket = os.getenv("S3_BUCKET")
    if not bucket:
        # S3 upload is optional — no bucket configured, nothing to do.
        return

    # Strip the base_path prefix to build the S3 key.
    # Normalise separators so stripping works on any OS.
    norm_local = local_path.replace("\\", "/")
    norm_base  = base_path.rstrip("/").replace("\\", "/") + "/"
    key = norm_local[len(norm_base):] if norm_local.startswith(norm_base) else norm_local

    s3 = boto3.client("s3")

    try:
        s3.upload_file(local_path, bucket, key)
        logger.info(
            f"Uploaded {local_path} to s3://{bucket}/{key}"
        )
    except Exception as exc:
        logger.warning(
            f"Failed to upload {local_path} to S3: {exc}"
        )
