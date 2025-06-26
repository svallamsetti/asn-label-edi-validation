import os
import json
import tempfile
import urllib.parse

import boto3

from .validator import validate


def lambda_handler(event, context):
    """AWS Lambda entrypoint triggered by S3 uploads."""
    records = event.get("Records", [])
    bucket = None
    label_key = None
    edi_key = None

    for record in records:
        s3_info = record.get("s3", {})
        bucket = s3_info.get("bucket", {}).get("name") or bucket
        key = s3_info.get("object", {}).get("key")
        if key:
            key = urllib.parse.unquote_plus(key)
            if key.lower().endswith((".pdf", ".png", ".jpg", ".jpeg")):
                label_key = key
            elif key.lower().endswith((".edi", ".txt")):
                edi_key = key

    s3 = boto3.client("s3")

    if bucket and (not label_key or not edi_key):
        base_key = label_key or edi_key
        base, _ = os.path.splitext(base_key)

        if not label_key:
            for ext in (".pdf", ".png", ".jpg", ".jpeg"):
                candidate = base + ext
                try:
                    s3.head_object(Bucket=bucket, Key=candidate)
                    label_key = candidate
                    break
                except Exception as exc:  # type: ignore
                    if getattr(exc, "response", {}).get("Error", {}).get("Code") != "404":
                        raise

        if not edi_key:
            for ext in (".edi", ".txt"):
                candidate = base + ext
                try:
                    s3.head_object(Bucket=bucket, Key=candidate)
                    edi_key = candidate
                    break
                except Exception as exc:  # type: ignore
                    if getattr(exc, "response", {}).get("Error", {}).get("Code") != "404":
                        raise

    if not bucket or not label_key or not edi_key:
        print("Waiting for companion file")
        return {"success": False, "error": "Missing label or EDI file"}
    with tempfile.TemporaryDirectory() as tmpdir:
        label_path = os.path.join(tmpdir, os.path.basename(label_key))
        edi_path = os.path.join(tmpdir, os.path.basename(edi_key))
        s3.download_file(bucket, label_key, label_path)
        s3.download_file(bucket, edi_key, edi_path)
        result = validate(label_path, edi_path)
        print(json.dumps(result, indent=2))
        return result
