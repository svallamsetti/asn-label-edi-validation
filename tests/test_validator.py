import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from asn_validator.validator import compare_label_and_edi


def test_compare_packs():
    label = {
        "qr_blocks": [
            {
                "asn_number": "000123",
                "serial_number": "1J0001",
                "quantity": "10",
                "po_line_number": "1",
                "part_number": "PT001",
            }
        ]
    }
    edi = {
        "asn_number": "000123",
        "po_number": "PO12345",
        "packs": [{"serial_number": "1J0001", "quantity": "10"}],
        "line_items": [{"po_line_number": "1", "part_number": "PT001", "quantity": "10"}]
    }
    result = compare_label_and_edi(label, edi)
    assert result["success"] is True
    assert result["checks"][0]["asn_number"] == "match"
