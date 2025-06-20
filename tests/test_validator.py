import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from asn_validator.validator import compare_label_and_edi


def test_compare_packs():
    label = {
        "qr_blocks": [
            {
                "asn_number": "000123",
                "po_number": "PO12345",
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
    assert result["checks"][0]["po_number"] == "match"
    assert result["checks"][0]["serial_number"] == "match"
    assert result["checks"][0]["quantity"] == "match"
    assert result["checks"][0]["po_line_number"] == "match"
    assert result["checks"][0]["part_number"] == "match"


def test_line_item_quantity_sum():
    label = {
        "qr_blocks": [
            {
                "serial_number": "1J1",
                "po_line_number": "1",
                "part_number": "PT001",
                "quantity": "5",
            },
            {
                "serial_number": "1J2",
                "po_line_number": "1",
                "part_number": "PT001",
                "quantity": "5",
            },
        ]
    }
    edi = {
        "packs": [
            {"serial_number": "1J1", "quantity": "5"},
            {"serial_number": "1J2", "quantity": "5"},
        ],
        "line_items": [
            {"po_line_number": "1", "part_number": "PT001", "quantity": "10"}
        ],
    }
    result = compare_label_and_edi(label, edi)
    assert result["success"] is True
    assert result["totals"]["1"] == "match"
    assert result["line_items"]["1"] == "match"


def test_totals_fail_on_individual_mismatch():
    label = {
        "qr_blocks": [
            {
                "serial_number": "1J1",
                "po_line_number": "1",
                "part_number": "PT001",
                "quantity": "12",
            },
            {
                "serial_number": "1J2",
                "po_line_number": "1",
                "part_number": "PT001",
                "quantity": "8",
            },
        ]
    }
    edi = {
        "packs": [
            {"serial_number": "1J1", "quantity": "11"},
            {"serial_number": "1J2", "quantity": "8"},
        ],
        "line_items": [
            {"po_line_number": "1", "part_number": "PT001", "quantity": "20"}
        ],
    }
    result = compare_label_and_edi(label, edi)
    assert result["totals"]["1"] == "mismatch"
    assert result["success"] is False
    assert any("packs" in e for e in result["errors"])


def test_po_number_mismatch():
    label = {"qr_blocks": [{"po_number": "PO1", "serial_number": "1J1", "po_line_number": "1", "part_number": "PT001", "quantity": "5"}]}
    edi = {
        "po_number": "PO2",
        "packs": [{"serial_number": "1J1", "quantity": "5"}],
        "line_items": [{"po_line_number": "1", "part_number": "PT001", "quantity": "5"}]
    }
    result = compare_label_and_edi(label, edi)
    assert result["checks"][0]["po_number"] == "mismatch"
    assert result["line_items"]["1"] == "match"
    assert result["success"] is False


def test_error_messages_present():
    label = {"qr_blocks": [{"po_number": "PO1", "serial_number": "1J1", "po_line_number": "1", "part_number": "PT001", "quantity": "5"}]}
    edi = {
        "po_number": "PO2",
        "packs": [{"serial_number": "1J1", "quantity": "5"}],
        "line_items": [{"po_line_number": "1", "part_number": "PT001", "quantity": "5"}]
    }
    result = compare_label_and_edi(label, edi)
    assert result["success"] is False
    assert result["errors"]
    assert any("PO number" in e for e in result["errors"])
