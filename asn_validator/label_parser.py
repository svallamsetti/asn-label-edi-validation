from typing import Dict, Any
import re

try:
    import pytesseract
except Exception:
    pytesseract = None

try:
    from pdf2image import convert_from_path
    from PIL import Image
    from pyzbar.pyzbar import decode
except Exception:
    convert_from_path = None
    Image = None
    decode = None


def _extract_codes_from_image(img) -> tuple[list[str], list[str]]:
    """Return QR code strings and all other barcode values."""
    if decode is None:
        raise RuntimeError("pyzbar is required for QR code parsing")
    qr_values: list[str] = []
    barcode_values: list[str] = []
    for code in decode(img):
        value = code.data.decode("utf-8")
        if code.type == "QRCODE":
            qr_values.append(value)
        else:
            barcode_values.append(value)
    return qr_values, barcode_values


def _parse_text_fields(text: str) -> Dict[str, str]:
    """Extract key fields from OCR text."""
    address_patterns = {
        'ship_from': r'SHIP\s*FROM[:\s]*(.*?)(?=SHIP\s*TO|$)',
        'ship_to': r'SHIP\s*TO[:\s]*(.*?)(?=P/?N|PO\s*NO|PO\s*LINE|QTY|DESCRIPTION|$)',
    }
    fields: Dict[str, str] = {}
    for key, pat in address_patterns.items():
        m = re.search(pat, text, re.IGNORECASE | re.DOTALL)
        fields[key] = m.group(1).strip() if m else ''

    other_patterns = {
        'qty': r'QTY(?:\(Q\))?[:\s]*([^\n]+)',
        'part_number': r'P/?N(?:\(P\))?[:\s]*([^\n]+)',
        'description': r'DESCRIPTION[:\s]*([^\n]+)',
        'po_number': r'PO\s*NO\.?:?\s*([^\n]+)',
        'po_line_number': r'PO\s*LINE\s*NO\.?:?\s*([^\n]+)',
        'prod_date': r'PROD\s*DATE[:\s]*([^\n]+)',
        'lot_number': r'LOT\s*NO\.?:?\s*([^\n]+)',
        'qml': r'QML[:\s]*([^\n]+)',
        'pcd': r'PCD[:\s]*([^\n]+)',
        'exp_date': r'EXP\s*DATE[:\s]*([^\n]+)',
    }
    for key, pat in other_patterns.items():
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            val = m.group(1).strip()
            if key in ('po_number', 'po_line_number'):
                val = val.split()[0]
            fields[key] = val
        else:
            fields[key] = ''
    m = re.search(r'\b([125]J)\b', text)
    fields['label_type'] = m.group(1) if m else ''
    return fields


def _extract_text_fields_from_image(img) -> Dict[str, str]:
    if pytesseract is None:
        raise RuntimeError('pytesseract is required for text extraction')
    text = pytesseract.image_to_string(img)
    return _parse_text_fields(text)


def parse_label(path: str) -> Dict[str, Any]:
    """Parse an ASN label PDF or image and return extracted QR and barcode data."""
    qr_data: list[str] = []
    barcodes: list[str] = []
    text_fields: Dict[str, str] = {}
    if path.lower().endswith('.pdf'):
        if convert_from_path is None:
            raise RuntimeError('pdf2image is required to parse PDF labels')
        pages = convert_from_path(path)
        for page in pages:
            qrs, codes = _extract_codes_from_image(page)
            qr_data.extend(qrs)
            barcodes.extend(codes)
            try:
                fields = _extract_text_fields_from_image(page)
                for k, v in fields.items():
                    if v and not text_fields.get(k):
                        text_fields[k] = v
            except Exception:
                pass
    else:
        if Image is None:
            raise RuntimeError('Pillow is required to parse image labels')
        img = Image.open(path)
        qrs, codes = _extract_codes_from_image(img)
        qr_data.extend(qrs)
        barcodes.extend(codes)
        try:
            fields = _extract_text_fields_from_image(img)
            for k, v in fields.items():
                if v and not text_fields.get(k):
                    text_fields[k] = v
        except Exception:
            pass
    parsed_blocks = []
    seen_serials = set()
    for s in qr_data:
        block = _parse_qr_string(s)
        serial = block.get("serial_number")
        if serial and serial not in seen_serials:
            seen_serials.add(serial)
            parsed_blocks.append(block)
    if text_fields:
        print("Extracted text fields:", text_fields)
    return {
        "qr_blocks": parsed_blocks,
        "barcodes": list(dict.fromkeys(barcodes)),
        "text_fields": text_fields,
    }


def _parse_qr_string(data: str) -> Dict[str, Any]:
    """Parse QR string according to documented format."""
    # QR example format:
    # [)>\x1e06\x1dASNNO\x1d1JSerial\x1dLot\x1dPO\x1dPOLine\x1dPart\x1dDesc\x1dQty\x1dUOM
    # Replace ASCII group/record separators with a placeholder and split.
    # Do not discard empty fields so the mapping stays aligned even when
    # optional fields are missing.
    parts = data.replace('\u001e', '?').replace('\u001d', '?').split('?')
    mapping = [
        "indicator",
        "message_type",
        "asn_number",
        "serial_number",
        "lot_number",
        "po_number",
        "po_line_number",
        "part_number",
        "part_description",
        "quantity",
        "uom",
        "production_date",
        "expiration_date",
        "qml",
        "pcd",
        "supplier_serial_number",
    ]
    result = {}
    for idx, field in enumerate(mapping):
        if idx < len(parts):
            value = parts[idx]
            if value:
                result[field] = value
    return result
