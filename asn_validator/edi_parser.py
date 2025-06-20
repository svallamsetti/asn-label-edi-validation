from typing import Dict, Any, List


def parse_x12(contents: str) -> Dict[str, Any]:
    """Parse a minimal subset of X12 856 data used for validation."""
    segments = [s.strip() for s in contents.strip().split('~') if s.strip()]

    data: Dict[str, Any] = {"line_items": []}
    current_hl = ""
    current_item: Dict[str, Any] | None = None
    current_pack: Dict[str, Any] | None = None

    for seg in segments:
        parts = seg.split('*')
        tag = parts[0]

        if tag == 'BSN' and len(parts) > 2:
            data['asn_number'] = parts[2]

        elif tag == 'PRF' and len(parts) > 1:
            data['po_number'] = parts[1]

        elif tag == 'HL' and len(parts) > 3:
            current_hl = parts[3]
            if current_hl == 'I':
                current_item = {}
                data['line_items'].append(current_item)
            elif current_hl == 'P':
                current_pack = {}
                data.setdefault('packs', []).append(current_pack)

        elif tag == 'LIN' and current_item is not None:
            # LIN*PO_LINE_NO**BP*PARTNO
            if len(parts) > 1:
                current_item['po_line_number'] = parts[1]
            for i, val in enumerate(parts):
                if val in {'BP', 'VP', 'PN'} and i + 1 < len(parts):
                    current_item['part_number'] = parts[i + 1]
                    break

        elif tag == 'SN1':
            qty = parts[2] if len(parts) > 2 else ''
            uom = parts[3] if len(parts) > 3 else ''
            if current_hl == 'I' and current_item is not None:
                current_item['quantity'] = qty
                if uom:
                    current_item['uom'] = uom
            elif current_hl == 'P' and current_pack is not None:
                current_pack['quantity'] = qty
                if uom:
                    current_pack['uom'] = uom
            else:
                data['quantity'] = qty
                if uom:
                    data['uom'] = uom

        elif tag == 'MAN' and current_hl == 'P' and current_pack is not None:
            if len(parts) > 2:
                current_pack['serial_number'] = parts[2]

    return data


def parse_edifact(contents: str) -> Dict[str, Any]:
    # EDIFACT segments are separated by an apostrophe. Lines may contain
    # additional whitespace or newlines which should be ignored.
    segments = [s.strip() for s in contents.strip().split("'") if s.strip()]
    data = {}
    for seg in segments:
        seg = seg.strip()
        parts = seg.split('+')
        tag = parts[0]
        if tag == 'BGM' and len(parts) > 2:
            data['asn_number'] = parts[2]
        elif tag == 'LIN':
            data.setdefault('line_items', []).append({
                'po_line_number': parts[1],
                'part_number': parts[2] if len(parts) > 2 else '',
            })
        elif tag == 'QTY' and data.get('line_items'):
            qty_parts = parts[1].split(':')
            data['line_items'][-1]['quantity'] = qty_parts[1]
            if len(qty_parts) > 2:
                data['line_items'][-1]['uom'] = qty_parts[2]
    return data


def parse_edi(path: str) -> Dict[str, Any]:
    with open(path, 'r', encoding='utf-8') as f:
        contents = f.read()
    if '~' in contents and '*' in contents:
        return parse_x12(contents)
    return parse_edifact(contents)
