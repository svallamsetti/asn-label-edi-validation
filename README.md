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

## Notes

Image, PDF and QR parsing requires `pdf2image`, `Pillow` and `pyzbar` to
be installed. These libraries are not included by default.
