"""
tests/unit/test_s3_uploader.py

Unit tests for lakehouse/s3_uploader.py — written BEFORE implementation (TDD).

All tests mock boto3 and os.environ so no AWS credentials or network
access is required.
"""

import logging
from unittest.mock import MagicMock, patch

from lakehouse.s3_uploader import upload_file_to_s3

LOCAL_PATH = "data/gold/gold_vwap_1min/year=2026/month=04/day=23/part-abc123.parquet"
BASE_PATH  = "data/gold"


# ── Test 1 — No upload when S3_BUCKET is not set ─────────────────────────────

def test_upload_skipped_when_no_bucket():
    """
    upload_file_to_s3() must be a no-op when S3_BUCKET is not set.
    """
    with patch.dict("os.environ", {}, clear=True), patch("lakehouse.s3_uploader.boto3") as mock_boto3:
        upload_file_to_s3(LOCAL_PATH, BASE_PATH)
        mock_boto3.client.assert_not_called()


def test_upload_triggered_when_bucket_set():
    """
    upload_file_to_s3() must call boto3 upload_file when S3_BUCKET is set.
    """
    mock_s3 = MagicMock()
    with patch.dict("os.environ", {"S3_BUCKET": "my-bucket"}), patch("lakehouse.s3_uploader.boto3.client", return_value=mock_s3):
        upload_file_to_s3(LOCAL_PATH, BASE_PATH)
        mock_s3.upload_file.assert_called_once()


# ── Test 2 — Correct S3 key structure ────────────────────────────────────────

def test_s3_key_strips_base_path():
    """
    The S3 key must strip the base_path prefix, preserving the rest.

    Input:  data/gold/gold_vwap_1min/year=2026/month=04/day=23/part-abc.parquet
    Output: gold_vwap_1min/year=2026/month=04/day=23/part-abc.parquet
    """
    mock_s3 = MagicMock()
    with patch.dict("os.environ", {"S3_BUCKET": "my-bucket"}), patch("lakehouse.s3_uploader.boto3.client", return_value=mock_s3):
        upload_file_to_s3(LOCAL_PATH, BASE_PATH)

    call_args = mock_s3.upload_file.call_args[0]
    s3_key = call_args[2]

    assert s3_key == "gold_vwap_1min/year=2026/month=04/day=23/part-abc123.parquet"
    assert not s3_key.startswith("data/gold/")


# ── Test 3 — Upload failure does not raise ────────────────────────────────────

def test_upload_failure_does_not_raise(caplog):
    """
    If boto3 raises an exception, upload_file_to_s3() must catch it and
    log a warning — never propagate the exception.
    """
    mock_s3 = MagicMock()
    mock_s3.upload_file.side_effect = Exception("Connection timeout")

    with patch.dict("os.environ", {"S3_BUCKET": "my-bucket"}), patch("lakehouse.s3_uploader.boto3.client", return_value=mock_s3), caplog.at_level(logging.WARNING, logger="lakehouse.s3_uploader"):
        upload_file_to_s3(LOCAL_PATH, BASE_PATH)

    assert any("Failed to upload" in r.message for r in caplog.records)


# ── Test 4 — Successful upload logs info ─────────────────────────────────────

def test_successful_upload_logs_info(caplog):
    """
    A successful upload must log an INFO message with the S3 URI.
    """
    mock_s3 = MagicMock()

    with patch.dict("os.environ", {"S3_BUCKET": "my-bucket"}), patch("lakehouse.s3_uploader.boto3.client", return_value=mock_s3), caplog.at_level(logging.INFO, logger="lakehouse.s3_uploader"):
        upload_file_to_s3(LOCAL_PATH, BASE_PATH)

    assert any("s3://my-bucket" in r.message for r in caplog.records)
