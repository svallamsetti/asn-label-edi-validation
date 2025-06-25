import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from asn_validator.label_parser import _parse_qr_string, _parse_text_fields


def test_parse_qr_string_fields():
    data = "[)>\x1e06\x1dASN1\x1d1J123\x1d\x1dPO\x1d01\x1dPART\x1dDESC\x1d5\x1dEA\x1d20240101\x1d\x1d\x1d\x1dSUPSER"
    result = _parse_qr_string(data)
    assert result["serial_number"] == "1J123"
    assert "lpn" not in result
    assert result["supplier_serial_number"] == "SUPSER"
    assert result["po_number"] == "PO"
    assert result["quantity"] == "5"


def test_parse_text_fields():
    text = """
    SHIP FROM: SUP
    SHIP TO: CUST
    PO NO. PO123
    PO LINE NO. 1
    P/N: PT001
    DESCRIPTION: Widget
    QTY: 10
    PROD DATE: 20240101
    LOT NO.: LOT1
    EXP DATE: 20250101
    """
    fields = _parse_text_fields(text)
    assert fields["ship_from"] == "SUP"
    assert fields["ship_to"] == "CUST"
    assert fields["po_number"] == "PO123"
    assert fields["po_line_number"] == "1"
    assert fields["part_number"] == "PT001"
    assert fields["qty"] == "10"
