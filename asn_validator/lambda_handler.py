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

    if not bucket or not label_key or not edi_key:
        print("Event must include both label and EDI files")
        return {"success": False, "error": "Missing label or EDI file"}

    s3 = boto3.client("s3")
    with tempfile.TemporaryDirectory() as tmpdir:
        label_path = os.path.join(tmpdir, os.path.basename(label_key))
        edi_path = os.path.join(tmpdir, os.path.basename(edi_key))
        s3.download_file(bucket, label_key, label_path)
        s3.download_file(bucket, edi_key, edi_path)
        result = validate(label_path, edi_path)
        print(json.dumps(result, indent=2))
        return result
