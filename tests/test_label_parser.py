import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from asn_validator.label_parser import _parse_qr_string


def test_parse_qr_string_fields():
    data = "[)>\x1e06\x1dASN1\x1d1J123\x1d\x1dPO\x1d01\x1dPART\x1dDESC\x1d5\x1dEA\x1d20240101\x1d\x1d\x1d\x1dSUPSER"
    result = _parse_qr_string(data)
    assert result["serial_number"] == "1J123"
    assert "lpn" not in result
    assert result["supplier_serial_number"] == "SUPSER"
    assert result["po_number"] == "PO"
    assert result["quantity"] == "5"
