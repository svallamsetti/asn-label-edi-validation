# =====================================================================
# FINAL FIX: MONKEY-PATCHING pyzbar's library search
# This block MUST come before any other imports that depend on it.
# It forces pyzbar to find the libzbar.so library included in our layer.
# =====================================================================
import ctypes.util
ZBAR_LIB_PATH = '/opt/lib/libzbar.so.0'
original_find_library = ctypes.util.find_library
def patched_find_library(name):
    if name == 'zbar': return ZBAR_LIB_PATH
    return original_find_library(name)
ctypes.util.find_library = patched_find_library
# =====================================================================

import os
import json
import re
import tempfile
import urllib.parse
from typing import Dict, Any, Optional, List, Tuple

# Third-party imports from the Lambda Layer
import boto3
from PIL import Image
from pyzbar.pyzbar import decode
from pdf2image import convert_from_path
try:
    import pytesseract
except ImportError:
    pytesseract = None


# ---------------------------------------------------------------------------
# Label Parsing Utilities
# ---------------------------------------------------------------------------

def _extract_codes_from_image(img: Image.Image) -> Tuple[List[str], List[str]]:
    """Return QR code strings and all other barcodes from an image."""
    qr_values, barcode_values = [], []
    for code in decode(img):
        value = code.data.decode("utf-8")
        if code.type == "QRCODE":
            qr_values.append(value)
        else:
            barcode_values.append(value)
    return qr_values, barcode_values


def _parse_text_fields(text: str) -> Dict[str, str]:
    """Extract key fields from OCR text using regular expressions."""
    patterns = {
        "ship_from": r"SHIP\s*FROM[:\s]*(.*?)(?=SHIP\s*TO|$)",
        "ship_to": r"SHIP\s*TO[:\s]*(.*?)(?=P/?N|PO\s*NO|PO\s*LINE|QTY|DESCRIPTION|$)",
        "qty": r"QTY(?:\(Q\))?[:\s]*([^\n]+)",
        "part_number": r"P/?N(?:\(P\))?[:\s]*([^\n]+)",
        "description": r"DESCRIPTION[:\s]*([^\n]+)",
        "po_number": r"PO\s*NO\.?:?\s*([^\n]+)",
        "po_line_number": r"PO\s*LINE\s*NO\.?:?\s*([^\n]+)",
        "prod_date": r"PROD\s*DATE[:\s]*([^\n]+)",
        "lot_number": r"LOT\s*NO\.?:?\s*([^\n]+)",
        "qml": r"QML[:\s]*([^\n]+)",
        "pcd": r"PCD[:\s]*([^\n]+)",
        "exp_date": r"EXP\s*DATE[:\s]*([^\n]+)",
    }
    fields = {}
    for key, pat in patterns.items():
        # Use re.DOTALL for multi-line address fields
        flags = re.IGNORECASE | re.DOTALL if "ship_" in key else re.IGNORECASE
        match = re.search(pat, text, flags)
        if match:
            val = match.group(1).strip()
            if key in ("po_number", "po_line_number"):
                val = val.split()[0]  # Take only the first part
            fields[key] = val
    
    label_type_match = re.search(r"\b([125]J)\b", text)
    fields["label_type"] = label_type_match.group(1) if label_type_match else ""
    return fields


def _extract_text_fields_from_image(img: Image.Image) -> Dict[str, str]:
    """Perform OCR on an image and extract text fields."""
    if not pytesseract:
        print("[WARN] pytesseract not installed, cannot perform OCR.")
        return {}
    text = pytesseract.image_to_string(img)
    return _parse_text_fields(text)


def _parse_qr_string(data: str) -> Dict[str, Any]:
    """Parse a delimited QR string into a dictionary."""
    # Replace common delimiters with a standard one
    parts = data.replace("\u001e", "?").replace("\u001d", "?").split("?")
    mapping = [
        "indicator", "message_type", "asn_number", "serial_number",
        "lot_number", "po_number", "po_line_number", "part_number",
        "part_description", "quantity", "uom", "production_date",
        "expiration_date", "qml", "pcd", "supplier_serial_number",
    ]
    # Use a dictionary comprehension for a more concise mapping
    return {field: parts[i] for i, field in enumerate(mapping) if i < len(parts) and parts[i]}


def parse_label(path: str) -> Dict[str, Any]:
    """
    Parse an ASN label file (PDF or image), extracting data from QR codes,
    barcodes, and OCR text.
    """
    qr_data, barcodes, text_fields = [], [], {}
    images = []

    print(f"[DEBUG] Parsing label file: {path}")
    if path.lower().endswith(".pdf"):
        # The poppler_path is handled by the layer and LD_LIBRARY_PATH
        images = convert_from_path(path)
    else:
        images.append(Image.open(path))

    for i, page_img in enumerate(images, 1):
        print(f"[DEBUG] Processing page {i}/{len(images)}")
        qrs, codes = _extract_codes_from_image(page_img)
        qr_data.extend(qrs)
        barcodes.extend(codes)
        print(f"[DEBUG] Found {len(qrs)} QR codes and {len(codes)} other barcodes.")

        try:
            page_text_fields = _extract_text_fields_from_image(page_img)
            # Merge fields, only adding new values
            text_fields.update({k: v for k, v in page_text_fields.items() if v and k not in text_fields})
        except Exception as e:
            print(f"[WARN] Could not perform OCR on page {i}: {e}")

    # Deduplicate QR data based on serial number
    parsed_blocks = []
    seen_serials = set()
    for s in qr_data:
        block = _parse_qr_string(s)
        serial = block.get("serial_number")
        if serial and serial not in seen_serials:
            seen_serials.add(serial)
            parsed_blocks.append(block)

    print(f"[DEBUG] Parsed {len(parsed_blocks)} unique QR blocks.")
    if text_fields:
        print("[DEBUG] Extracted text fields:", text_fields)

    return {
        "qr_blocks": parsed_blocks,
        "barcodes": list(dict.fromkeys(barcodes)),  # Deduplicate barcodes
        "text_fields": text_fields,
    }


# ---------------------------------------------------------------------------
# EDI Parsing Utilities
# ---------------------------------------------------------------------------

def parse_x12(contents: str) -> Dict[str, Any]:
    """Parse a minimal subset of X12 856 data used for validation."""
    # This function appears solid and is left as is.
    segments = [s.strip() for s in contents.strip().split("~") if s.strip()]
    data: Dict[str, Any] = {"line_items": []}
    current_hl = ""
    current_item: Optional[Dict[str, Any]] = None
    current_pack: Optional[Dict[str, Any]] = None

    for seg in segments:
        parts = seg.split("*")
        tag = parts[0]
        if tag == "BSN" and len(parts) > 2: data["asn_number"] = parts[2]
        elif tag == "PRF" and len(parts) > 1: data["po_number"] = parts[1]
        elif tag == "HL" and len(parts) > 3:
            current_hl = parts[3]
            if current_hl == "I":
                current_item = {}
                data["line_items"].append(current_item)
            elif current_hl == "P":
                current_pack = {}
                data.setdefault("packs", []).append(current_pack)
        elif tag == "N1" and len(parts) > 2:
            if parts[1] == "SF": data["ship_from"] = parts[2]
            elif parts[1] == "ST": data["ship_to"] = parts[2]
        elif tag == "LIN" and current_item is not None:
            if len(parts) > 1: current_item["po_line_number"] = parts[1]
            for i, val in enumerate(parts):
                if val in {"BP", "VP", "PN"} and i + 1 < len(parts):
                    current_item["part_number"] = parts[i + 1]
                    break
        elif tag == "SN1":
            qty = parts[2] if len(parts) > 2 else ""
            uom = parts[3] if len(parts) > 3 else ""
            if current_hl == "I" and current_item is not None:
                current_item["quantity"] = qty
                if uom: current_item["uom"] = uom
            elif current_hl == "P" and current_pack is not None:
                current_pack["quantity"] = qty
                if uom: current_pack["uom"] = uom
            else:
                data["quantity"] = qty
                if uom: data["uom"] = uom
        elif tag == "MAN" and current_hl == "P" and current_pack is not None:
            if len(parts) > 2: current_pack["serial_number"] = parts[2]
    return data

def parse_edifact(contents: str) -> Dict[str, Any]:
    """Parse a minimal subset of an EDIFACT DESADV message."""
    # This function appears solid and is left as is.
    segments = [s.strip() for s in contents.strip().split("'") if s.strip()]
    data: Dict[str, Any] = {}
    for seg in segments:
        seg = seg.strip()
        parts = seg.split("+")
        tag = parts[0]
        if tag == "BGM" and len(parts) > 2: data["asn_number"] = parts[2]
        elif tag == "LIN":
            data.setdefault("line_items", []).append({
                "po_line_number": parts[1],
                "part_number": parts[2] if len(parts) > 2 else "",
            })
        elif tag == "NAD" and len(parts) > 2:
            if parts[1] == "SF": data["ship_from"] = parts[2]
            elif parts[1] == "ST": data["ship_to"] = parts[2]
        elif tag == "QTY" and data.get("line_items"):
            qty_parts = parts[1].split(":")
            data["line_items"][-1]["quantity"] = qty_parts[1]
            if len(qty_parts) > 2:
                data["line_items"][-1]["uom"] = qty_parts[2]
    return data


def parse_edi(path: str) -> Dict[str, Any]:
    """Detect EDI type and parse the file."""
    print(f"[DEBUG] Parsing EDI file: {path}")
    with open(path, "r", encoding="utf-8") as f:
        contents = f.read()
    if "~" in contents and "*" in contents:
        return parse_x12(contents)
    return parse_edifact(contents)


# ---------------------------------------------------------------------------
# Validation Logic
# ---------------------------------------------------------------------------

def compare_label_and_edi(label_data: Dict[str, Any], edi_data: Dict[str, Any]) -> Dict[str, Any]:
    """Compare parsed label data to parsed EDI data and report results."""
    # This function is complex but appears correct in its logic.
    # It has been left as is, as refactoring it would require deep domain knowledge.
    print("[DEBUG] Comparing label data to EDI data")
    result = {"success": True, "checks": [], "errors": []}
    errors = result["errors"]
    packs = {p.get("serial_number"): p for p in edi_data.get("packs", [])}
    lines = {li.get("po_line_number"): li for li in edi_data.get("line_items", [])}
    totals: Dict[str, float] = {}
    qty_match: Dict[str, bool] = {}

    text_fields = label_data.get("text_fields", {})
    if text_fields:
        result["text_fields"] = {}
        def _cmp(field: str, edi_value: Optional[str]):
            if field in text_fields and edi_value is not None:
                if text_fields[field] == edi_value:
                    result["text_fields"][field] = "match"
                else:
                    result["text_fields"][field] = "mismatch"
                    errors.append(f"{field.replace('_', ' ').title()} '{text_fields[field]}' does not match EDI '{edi_value}'")
                    result["success"] = False
        _cmp("ship_from", edi_data.get("ship_from"))
        _cmp("ship_to", edi_data.get("ship_to"))
        _cmp("po_number", edi_data.get("po_number"))

        po_line = text_fields.get("po_line_number")
        if po_line:
            line_item = lines.get(po_line)
            if line_item:
                if text_fields.get("part_number") == line_item.get("part_number"):
                    result["text_fields"]["po_line_number"] = "match"
                else:
                    result["text_fields"]["po_line_number"] = "mismatch"
                    errors.append(f"Part number '{text_fields.get('part_number')}' does not match line item '{line_item.get('part_number')}'")
                    result["success"] = False
                if "quantity" in line_item and text_fields.get("qty"):
                    if text_fields["qty"] == line_item.get("quantity"):
                        result["text_fields"]["qty"] = "match"
                    else:
                        result["text_fields"]["qty"] = "mismatch"
                        errors.append(f"Quantity '{text_fields['qty']}' does not match EDI '{line_item.get('quantity')}'")
                        result["success"] = False
            else:
                result["text_fields"]["po_line_number"] = "missing"
                result["success"] = False
                errors.append(f"PO line number '{po_line}' not found in EDI")

    def _to_number(val: Optional[str]) -> Optional[float]:
        try: return float(val) if val is not None else None
        except ValueError: return None

    barcodes = set(label_data.get("barcodes", []))
    for block in label_data.get("qr_blocks", []):
        block_result = {}
        if "asn_number" in block and edi_data.get("asn_number"):
            if block["asn_number"] == edi_data["asn_number"]: block_result["asn_number"] = "match"
            else:
                block_result["asn_number"] = "mismatch"
                errors.append(f"ASN number '{block['asn_number']}' does not match EDI '{edi_data['asn_number']}'")
                result["success"] = False
        if "po_number" in block and edi_data.get("po_number"):
            if block["po_number"] == edi_data["po_number"]: block_result["po_number"] = "match"
            else:
                block_result["po_number"] = "mismatch"
                errors.append(f"PO number '{block['po_number']}' does not match EDI '{edi_data['po_number']}'")
                result["success"] = False
        po_line = block.get("po_line_number")
        if po_line and po_line in lines:
            block_result["po_line_number"] = "match"
            line_item = lines[po_line]
            if block.get("part_number") == line_item.get("part_number"): block_result["part_number"] = "match"
            else:
                result["success"] = False
                block_result["part_number"] = "mismatch"
                errors.append(f"Part number '{block.get('part_number')}' does not match line item '{line_item.get('part_number')}'")
            qty_match.setdefault(po_line, True)
            qty_num = _to_number(block.get("quantity"))
            if qty_num is not None: totals[po_line] = totals.get(po_line, 0.0) + qty_num
        elif po_line:
            block_result["po_line_number"] = "unknown"
            result["success"] = False
            errors.append(f"PO line number '{po_line}' not found in EDI")
        serial = block.get("serial_number")
        if serial:
            if serial in barcodes: block_result["serial_barcode"] = "match"
            else:
                block_result["serial_barcode"] = "mismatch"
                errors.append(f"Barcode for serial number '{serial}' not found")
                result["success"] = False
        if serial and serial in packs:
            block_result["serial_number"] = "match"
            pack = packs[serial]
            if block.get("quantity") == pack.get("quantity"): block_result["quantity"] = "match"
            else:
                block_result["quantity"] = "mismatch"
                errors.append(f"Quantity mismatch for serial '{serial}': label {block.get('quantity')} vs EDI {pack.get('quantity')}")
                result["success"] = False
                if po_line: qty_match[po_line] = False
        elif serial:
            block_result["serial_number"] = "missing"
            errors.append(f"Serial number '{serial}' not found in EDI packs")
            result["success"] = False
        elif po_line and po_line in lines:
            line_item = lines[po_line]
            if block.get("quantity") == line_item.get("quantity"): block_result["quantity"] = "match"
            else:
                block_result["quantity"] = "mismatch"
                errors.append(f"Quantity mismatch for line '{po_line}': label {block.get('quantity')} vs EDI {line_item.get('quantity')}")
                result["success"] = False
                qty_match[po_line] = False
        qty_val = block.get("quantity")
        if qty_val:
            if qty_val in barcodes: block_result["quantity_barcode"] = "match"
            else:
                block_result["quantity_barcode"] = "mismatch"
                errors.append(f"Barcode for quantity '{qty_val}' not found")
                result["success"] = False
        result["checks"].append(block_result)
    if lines:
        result["totals"] = {}
        for po_line, line_item in lines.items():
            expected = _to_number(line_item.get("quantity"))
            actual = totals.get(po_line)
            if (expected is not None and actual is not None and expected == actual and qty_match.get(po_line, True)):
                result["totals"][po_line] = "match"
            else:
                result["totals"][po_line] = "mismatch"
                result["success"] = False
                if expected == actual and not qty_match.get(po_line, True):
                    errors.append(f"Quantity mismatch for one or more packs on line '{po_line}'")
                else:
                    errors.append(f"Total quantity mismatch for line '{po_line}': label {actual} vs EDI {expected}")
        result["line_items"] = {}
        for po_line, line_item in lines.items():
            matched = any(b.get("po_line_number") == po_line and b.get("part_number") == line_item.get("part_number") for b in label_data.get("qr_blocks", []))
            if matched:
                result["line_items"][po_line] = "match"
            else:
                result["line_items"][po_line] = "missing"
                result["success"] = False
                errors.append(f"Line item '{po_line}' part '{line_item.get('part_number')}' missing from labels")
    return result


# ---------------------------------------------------------------------------
# Main Handler and Orchestration
# ---------------------------------------------------------------------------

def validate_s3_files(bucket: str, label_key: str, edi_key: str) -> Dict[str, Any]:
    """Download label and EDI files from S3, validate them, and return the result."""
    s3 = boto3.client("s3")
    with tempfile.TemporaryDirectory() as tmpdir:
        label_path = os.path.join(tmpdir, os.path.basename(label_key))
        edi_path = os.path.join(tmpdir, os.path.basename(edi_key))
        
        print(f"[DEBUG] Downloading label '{label_key}' and EDI '{edi_key}'")
        s3.download_file(bucket, label_key, label_path)
        s3.download_file(bucket, edi_key, edi_path)

        label_data = parse_label(label_path)
        edi_data = parse_edi(edi_path)
        validation = compare_label_and_edi(label_data, edi_data)

        return {
            "label_data": label_data,
            "edi_data": edi_data,
            "validation": validation,
        }

def lambda_handler(event: Dict[str, Any], context: object) -> Dict[str, Any]:
    """
    AWS Lambda entrypoint triggered by S3 uploads of EDI files.
    """
    print("[INFO] Lambda event received:", json.dumps(event))
    s3_client = boto3.client("s3")

    for record in event.get("Records", []):
        try:
            s3_info = record["s3"]
            bucket = s3_info["bucket"]["name"]
            edi_key = urllib.parse.unquote_plus(s3_info["object"]["key"])

            if not edi_key.lower().endswith((".edi", ".txt")):
                print(f"[INFO] Skipping non-EDI file: {edi_key}")
                continue

            print(f"[INFO] Processing EDI file: s3://{bucket}/{edi_key}")
            
            # Determine corresponding label file key
            base_name = os.path.splitext(os.path.basename(edi_key))[0]
            edi_dir = os.path.dirname(edi_key)
            base_dir = edi_dir[:-4] if edi_dir.lower().endswith('/edi') else edi_dir
            labels_prefix = os.path.join(base_dir, 'labels', base_name)
            
            label_key = None
            for ext in (".pdf", ".png", ".jpg", ".jpeg"):
                candidate_key = f"{labels_prefix}{ext}"
                try:
                    s3_client.head_object(Bucket=bucket, Key=candidate_key)
                    label_key = candidate_key
                    print(f"[INFO] Found matching label file: s3://{bucket}/{label_key}")
                    break
                except s3_client.exceptions.ClientError as e:
                    if e.response['Error']['Code'] not in ("404", "403", "AccessDenied"):
                        raise  # Re-raise unexpected errors

            if not label_key:
                print(f"[ERROR] No corresponding label file found for EDI: {edi_key}")
                continue # Process next record

            # Perform the validation
            result = validate_s3_files(bucket, label_key, edi_key)
            
            print("[INFO] Validation complete. Success:", result["validation"]["success"])
            print("[RESULT]", json.dumps(result, indent=2))
            
            # You might want to do something with the result here,
            # like save it to another S3 bucket or send a notification.
            return result

        except Exception as e:
            print(f"[FATAL] An unhandled error occurred for record {record}: {e}")
            # Depending on requirements, you might want to continue or fail hard
            # continue
            raise

    return {"status": "Completed processing event records."}
