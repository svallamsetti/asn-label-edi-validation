import json
from typing import Dict, Any, Optional

from .edi_parser import parse_edi
from .label_parser import parse_label


def compare_label_and_edi(label_data: Dict[str, Any], edi_data: Dict[str, Any]) -> Dict[str, Any]:
    result = {
        'success': True,
        'checks': []
    }

    packs = {p.get('serial_number'): p for p in edi_data.get('packs', [])}
    lines = {li.get('po_line_number'): li for li in edi_data.get('line_items', [])}
    totals: Dict[str, float] = {}

    def _to_number(val: Optional[str]) -> Optional[float]:
        try:
            return float(val) if val is not None else None
        except ValueError:
            return None

    for block in label_data.get('qr_blocks', []):
        block_result = {}

        if 'asn_number' in block and edi_data.get('asn_number'):
            if block['asn_number'] == edi_data['asn_number']:
                block_result['asn_number'] = 'match'
            else:
                block_result['asn_number'] = 'mismatch'
                result['success'] = False

        if 'po_number' in block and edi_data.get('po_number'):
            if block['po_number'] == edi_data['po_number']:
                block_result['po_number'] = 'match'
            else:
                block_result['po_number'] = 'mismatch'
                result['success'] = False

        po_line = block.get('po_line_number')
        if po_line and po_line in lines:
            block_result['po_line_number'] = 'match'
            line_item = lines[po_line]
            if block.get('part_number') == line_item.get('part_number'):
                block_result['part_number'] = 'match'
            else:
                result['success'] = False
                block_result['part_number'] = 'mismatch'
            qty_num = _to_number(block.get('quantity'))
            if qty_num is not None:
                totals[po_line] = totals.get(po_line, 0.0) + qty_num
        elif po_line:
            block_result['po_line_number'] = 'unknown'
            result['success'] = False

        serial = block.get('serial_number')
        if serial and serial in packs:
            block_result['serial_number'] = 'match'
            pack = packs[serial]
            if block.get('quantity') == pack.get('quantity'):
                block_result['quantity'] = 'match'
            else:
                block_result['quantity'] = 'mismatch'
                result['success'] = False
        elif serial:
            block_result['serial_number'] = 'missing'
            result['success'] = False
        elif po_line and po_line in lines:
            line_item = lines[po_line]
            if block.get('quantity') == line_item.get('quantity'):
                block_result['quantity'] = 'match'
            else:
                block_result['quantity'] = 'mismatch'
                result['success'] = False

        result['checks'].append(block_result)

    # Validate accumulated quantities for each line item
    if lines:
        result['totals'] = {}
        for po_line, line_item in lines.items():
            expected = _to_number(line_item.get('quantity'))
            actual = totals.get(po_line)
            if expected is not None and actual is not None and expected == actual:
                result['totals'][po_line] = 'match'
            else:
                result['totals'][po_line] = 'mismatch'
                result['success'] = False

        # Check that each line item exists on at least one label
        result['line_items'] = {}
        for po_line, line_item in lines.items():
            matched = any(
                b.get('po_line_number') == po_line and
                b.get('part_number') == line_item.get('part_number')
                for b in label_data.get('qr_blocks', [])
            )
            if matched:
                result['line_items'][po_line] = 'match'
            else:
                result['line_items'][po_line] = 'missing'
                result['success'] = False

    return result


def validate(label_path: str, edi_path: str) -> Dict[str, Any]:
    label_data = parse_label(label_path)
    edi_data = parse_edi(edi_path)
    validation = compare_label_and_edi(label_data, edi_data)
    return {
        'label': label_data,
        'edi': edi_data,
        'validation': validation
    }
