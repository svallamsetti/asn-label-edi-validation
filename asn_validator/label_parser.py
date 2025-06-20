from typing import Dict, Any

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


def parse_label(path: str) -> Dict[str, Any]:
    """Parse an ASN label PDF or image and return extracted QR and barcode data."""
    qr_data: list[str] = []
    barcodes: list[str] = []
    if path.lower().endswith('.pdf'):
        if convert_from_path is None:
            raise RuntimeError('pdf2image is required to parse PDF labels')
        pages = convert_from_path(path)
        for page in pages:
            qrs, codes = _extract_codes_from_image(page)
            qr_data.extend(qrs)
            barcodes.extend(codes)
    else:
        if Image is None:
            raise RuntimeError('Pillow is required to parse image labels')
        img = Image.open(path)
        qrs, codes = _extract_codes_from_image(img)
        qr_data.extend(qrs)
        barcodes.extend(codes)
    parsed_blocks = []
    seen_serials = set()
    for s in qr_data:
        block = _parse_qr_string(s)
        serial = block.get("serial_number")
        if serial and serial not in seen_serials:
            seen_serials.add(serial)
            parsed_blocks.append(block)
    return {"qr_blocks": parsed_blocks, "barcodes": list(dict.fromkeys(barcodes))}


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
