from typing import Dict, Any, List


def parse_x12(contents: str) -> Dict[str, Any]:
    # Split using the segment terminator and remove any leading/trailing
    # whitespace so that formatted EDI files with line breaks are handled
    # correctly (e.g. segments may start with a newline character).
    segments = [s.strip() for s in contents.strip().split('~') if s.strip()]
    data = {}
    for seg in segments:
        seg = seg.strip()
        parts = seg.split('*')
        tag = parts[0]
        if tag == 'BSN':
            data['asn_number'] = parts[2]
        elif tag == 'PO1':
            data.setdefault('line_items', []).append({
                'po_line_number': parts[1],
                'quantity': parts[2],
                'uom': parts[3],
                'part_number': parts[6],
            })
        elif tag == 'HL' and len(parts) > 3 and parts[3] == 'S':
            data['serial_number'] = parts[1]
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
