import textwrap
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from asn_validator.edi_parser import parse_x12

def test_parse_x12_handles_newlines():
    edi = textwrap.dedent(
        """
        GS*SH*XPELTEST*RIVIAN-TEST*20250406*2144*72*X*005010~
        ST*856*0001~
        BSN*00*000123*20250406~
        HL*1**S~
        PO1*1*12*EA***BP*PT001~
        """
    )
    data = parse_x12(edi)
    assert data["asn_number"] == "000123"
    assert data["serial_number"] == "1"
    assert data["line_items"][0]["po_line_number"] == "1"
    assert data["line_items"][0]["quantity"] == "12"

