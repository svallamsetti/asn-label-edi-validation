import json
from typing import Dict, Any, List

try:
    from pdf2image import convert_from_path
    from PIL import Image
    from pyzbar.pyzbar import decode
except Exception:
    convert_from_path = None
    Image = None
    decode = None


def _extract_qr_from_image(img) -> List[str]:
    if decode is None:
        raise RuntimeError("pyzbar is required for QR code parsing")
    results = []
    for code in decode(img):
        if code.type in {"QRCODE", "CODE128", "CODE39"}:
            results.append(code.data.decode('utf-8'))
    return results


def parse_label(path: str) -> Dict[str, Any]:
    """Parse an ASN label PDF or image and return extracted QR data."""
    qr_data: List[str] = []
    if path.lower().endswith('.pdf'):
        if convert_from_path is None:
            raise RuntimeError('pdf2image is required to parse PDF labels')
        pages = convert_from_path(path)
        for page in pages:
            qr_data.extend(_extract_qr_from_image(page))
    else:
        if Image is None:
            raise RuntimeError('Pillow is required to parse image labels')
        img = Image.open(path)
        qr_data.extend(_extract_qr_from_image(img))
    parsed_blocks = [_parse_qr_string(s) for s in qr_data]
    return {"qr_blocks": parsed_blocks}


def _parse_qr_string(data: str) -> Dict[str, Any]:
    """Parse QR string according to documented format."""
    # QR example format:
    # [)>\x1e06\x1dASNNO\x1d1JSerial\x1dLot\x1dPO\x1dPOLine\x1dPart\x1dDesc\x1dQty\x1dUOM
    parts = data.replace('\u001e', '?').replace('\u001d', '?').split('?')
    # Remove empty entries
    parts = [p for p in parts if p]
    mapping = [
        "indicator",
        "message_type",
        "asn_number",
        "lpn",
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
        "serial_number",
    ]
    result = {}
    for idx, field in enumerate(mapping):
        if idx < len(parts):
            result[field] = parts[idx]
    return result
