import json
from typing import Dict, Any, Optional

from .edi_parser import parse_edi
from .label_parser import parse_label


def compare_label_and_edi(label_data: Dict[str, Any], edi_data: Dict[str, Any]) -> Dict[str, Any]:
    result = {
        'success': True,
        'checks': [],
        'errors': []
    }

    errors = result['errors']

    packs = {p.get('serial_number'): p for p in edi_data.get('packs', [])}
    lines = {li.get('po_line_number'): li for li in edi_data.get('line_items', [])}
    totals: Dict[str, float] = {}
    qty_match: Dict[str, bool] = {}

    # compare text fields extracted from the label
    text_fields = label_data.get('text_fields', {})
    if text_fields:
        result['text_fields'] = {}
        def _cmp(field, edi_value):
            if field in text_fields and edi_value is not None:
                if text_fields[field] == edi_value:
                    result['text_fields'][field] = 'match'
                else:
                    result['text_fields'][field] = 'mismatch'
                    errors.append(
                        f"{field.replace('_', ' ').title()} '{text_fields[field]}' does not match EDI '{edi_value}'"
                    )
                    result['success'] = False

        _cmp('ship_from', edi_data.get('ship_from'))
        _cmp('ship_to', edi_data.get('ship_to'))
        _cmp('po_number', edi_data.get('po_number'))

        po_line = text_fields.get('po_line_number')
        if po_line:
            line_item = lines.get(po_line)
            if line_item:
                if text_fields.get('part_number') == line_item.get('part_number'):
                    result['text_fields']['po_line_number'] = 'match'
                else:
                    result['text_fields']['po_line_number'] = 'mismatch'
                    errors.append(
                        f"Part number '{text_fields.get('part_number')}' does not match line item '{line_item.get('part_number')}'"
                    )
                    result['success'] = False
                if 'quantity' in line_item and text_fields.get('qty'):
                    if text_fields['qty'] == line_item.get('quantity'):
                        result['text_fields']['qty'] = 'match'
                    else:
                        result['text_fields']['qty'] = 'mismatch'
                        errors.append(
                            f"Quantity '{text_fields['qty']}' does not match EDI '{line_item.get('quantity')}'"
                        )
                        result['success'] = False
            else:
                result['text_fields']['po_line_number'] = 'missing'
                result['success'] = False
                errors.append(f"PO line number '{po_line}' not found in EDI")

    def _to_number(val: Optional[str]) -> Optional[float]:
        try:
            return float(val) if val is not None else None
        except ValueError:
            return None

    barcodes = set(label_data.get('barcodes', []))

    for block in label_data.get('qr_blocks', []):
        block_result = {}
        serial = block.get('serial_number')

        if 'asn_number' in block and edi_data.get('asn_number'):
            if block['asn_number'] == edi_data['asn_number']:
                block_result['asn_number'] = 'match'
            else:
                block_result['asn_number'] = 'mismatch'
                errors.append(
                    f"ASN number '{block['asn_number']}' does not match EDI '{edi_data['asn_number']}'"
                )
                result['success'] = False

        if 'po_number' in block and edi_data.get('po_number'):
            if block['po_number'] == edi_data['po_number']:
                block_result['po_number'] = 'match'
            else:
                block_result['po_number'] = 'mismatch'
                errors.append(
                    f"PO number '{block['po_number']}' does not match EDI '{edi_data['po_number']}'"
                )
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
                errors.append(
                    f"Part number '{block.get('part_number')}' does not match line item '{line_item.get('part_number')}'"
                )
            qty_match.setdefault(po_line, True)
            qty_num = _to_number(block.get('quantity'))
            if qty_num is not None:
                totals[po_line] = totals.get(po_line, 0.0) + qty_num
        elif po_line:
            block_result['po_line_number'] = 'unknown'
            result['success'] = False
            errors.append(f"PO line number '{po_line}' not found in EDI")

        serial = block.get('serial_number')
        if serial:
            if serial in barcodes:
                block_result['serial_barcode'] = 'match'
            else:
                block_result['serial_barcode'] = 'mismatch'
                errors.append(f"Barcode for serial number '{serial}' not found")
                result['success'] = False

        if serial and serial in packs:
            block_result['serial_number'] = 'match'
            pack = packs[serial]
            if block.get('quantity') == pack.get('quantity'):
                block_result['quantity'] = 'match'
            else:
                block_result['quantity'] = 'mismatch'
                errors.append(
                    f"Quantity mismatch for serial '{serial}': label {block.get('quantity')} vs EDI {pack.get('quantity')}"
                )
                result['success'] = False
                if po_line:
                    qty_match[po_line] = False
        elif serial:
            block_result['serial_number'] = 'missing'
            errors.append(f"Serial number '{serial}' not found in EDI packs")
            result['success'] = False
        elif po_line and po_line in lines:
            line_item = lines[po_line]
            if block.get('quantity') == line_item.get('quantity'):
                block_result['quantity'] = 'match'
            else:
                block_result['quantity'] = 'mismatch'
                errors.append(
                    f"Quantity mismatch for line '{po_line}': label {block.get('quantity')} vs EDI {line_item.get('quantity')}"
                )
                result['success'] = False
                qty_match[po_line] = False

        qty_val = block.get('quantity')
        if qty_val:
            if qty_val in barcodes:
                block_result['quantity_barcode'] = 'match'
            else:
                block_result['quantity_barcode'] = 'mismatch'
                errors.append(f"Barcode for quantity '{qty_val}' not found")
                result['success'] = False

        result['checks'].append(block_result)

    # Validate accumulated quantities for each line item
    if lines:
        result['totals'] = {}
        for po_line, line_item in lines.items():
            expected = _to_number(line_item.get('quantity'))
            actual = totals.get(po_line)
            if (
                expected is not None
                and actual is not None
                and expected == actual
                and qty_match.get(po_line, True)
            ):
                result['totals'][po_line] = 'match'
            else:
                result['totals'][po_line] = 'mismatch'
                result['success'] = False
                if expected == actual and not qty_match.get(po_line, True):
                    errors.append(
                        f"Quantity mismatch for one or more packs on line '{po_line}'"
                    )
                else:
                    errors.append(
                        f"Total quantity mismatch for line '{po_line}': label {actual} vs EDI {expected}"
                    )

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
                errors.append(
                    f"Line item '{po_line}' part '{line_item.get('part_number')}' missing from labels"
                )

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
