# asn-label-edi-validation

This project validates an ASN label (PDF or image) against an EDI file
(X12 856 or EDIFACT DESADV). It extracts QR code information from the
label and compares it with key fields in the EDI message.

## Usage

```bash
python -m asn_validator.cli path/to/label.pdf path/to/edi.txt
```

The script prints a JSON structure with the parsed label data, parsed
EDI data and the result of all comparisons.

Each QR code block is parsed into fields such as `serial_number`,
`po_number`, `quantity`, and an optional `supplier_serial_number`. Only
non-empty fields are included in the output and duplicate serial numbers
are ignored.

## Notes

Image, PDF and QR parsing requires `pdf2image`, `Pillow` and `pyzbar` to
be installed. These libraries are not included by default.

The EDI parser tolerates formatted files that contain line breaks between
segments, so the input may include or omit newlines after each `~` or `'
` character.

The X12 parser also reads purchase order numbers from `PRF` segments,
line items via `LIN` with `SN1` for quantities, and pack information
from `HL` loops that contain `SN1` and `MAN` segments.

Each QR block is checked against the EDI data. The validator compares
`asn_number`, `po_number`, `po_line_number`, `part_number` and the
quantity of each label with the corresponding pack or line item.
Line item quantities are additionally summed across labels to ensure
the total matches the EDI quantity.
