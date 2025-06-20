import textwrap
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from asn_validator.edi_parser import parse_x12

def test_parse_x12_handles_newlines_and_loops():
    edi = textwrap.dedent(
        """
        GS*SH*XPELTEST*RIVIAN-TEST*20250406*2144*72*X*005010~
        ST*856*0001~
        BSN*00*000123*20250406~
        HL*1**S~
        HL*2*1*O~
        PRF*PO12345~
        HL*3*2*P~
        MAN*GM*1J0001~
        SN1**10*EA~
        HL*4*2*I~
        LIN*1**BP*PT001~
        SN1**12*EA~
        """
    )
    data = parse_x12(edi)
    assert data["asn_number"] == "000123"
    assert data["po_number"] == "PO12345"
    assert data["packs"][0]["serial_number"] == "1J0001"
    assert data["packs"][0]["quantity"] == "10"
    item = data["line_items"][0]
    assert item["po_line_number"] == "1"
    assert item["part_number"] == "PT001"
    assert item["quantity"] == "12"

