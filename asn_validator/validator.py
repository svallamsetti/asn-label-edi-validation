import json
from typing import Dict, Any

from .edi_parser import parse_edi
from .label_parser import parse_label


def compare_label_and_edi(label_data: Dict[str, Any], edi_data: Dict[str, Any]) -> Dict[str, Any]:
    result = {
        'success': True,
        'checks': []
    }

    packs = {p.get('serial_number'): p for p in edi_data.get('packs', [])}

    for block in label_data.get('qr_blocks', []):
        block_result = {}

        if 'asn_number' in block and edi_data.get('asn_number'):
            if block['asn_number'] == edi_data['asn_number']:
                block_result['asn_number'] = 'match'
            else:
                block_result['asn_number'] = 'mismatch'
                result['success'] = False

        if edi_data.get('line_items'):
            for line_item in edi_data['line_items']:
                if block.get('po_line_number') == line_item.get('po_line_number'):
                    if block.get('part_number') != line_item.get('part_number'):
                        result['success'] = False
                        block_result['part_number'] = 'mismatch'
                    if block.get('quantity') != line_item.get('quantity'):
                        result['success'] = False
                        block_result['quantity'] = 'mismatch'

        serial = block.get('serial_number')
        if serial and serial in packs:
            pack = packs[serial]
            if block.get('quantity') != pack.get('quantity'):
                block_result['pack_quantity'] = 'mismatch'
                result['success'] = False
        elif serial:
            block_result['pack'] = 'missing'
            result['success'] = False

        result['checks'].append(block_result)
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
