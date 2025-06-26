# asn-label-edi-validation

This project validates an ASN label (PDF or image) against an EDI file
(X12 856 or EDIFACT DESADV). It extracts QR code information from the
label and compares it with key fields in the EDI message.

## Usage

```bash
python -m asn_validator.cli path/to/label.pdf path/to/edi.txt
```

All functionality now resides in `asn_validator/lambda_function.py`. Modules in the `asn_validator` package simply re-export these functions.
The script prints a JSON structure with the parsed label data, parsed
EDI data and the result of all comparisons. Each QR block produces a
check entry indicating whether its serial number, quantity and other
fields matched the EDI packs or line items.

Each QR code block is parsed into fields such as `serial_number`,
`po_number`, `quantity`, and an optional `supplier_serial_number`. Only
non-empty fields are included in the output and duplicate serial numbers
are ignored.

In addition to QR data, any 1D barcodes found on the label are decoded.
The validator confirms that a barcode exists for each QR block's serial
number and quantity, ensuring the printed values match the encoded
barcodes.

Printed text on the label is also read via OCR (requires `pytesseract`).
Fields such as *SHIP FROM*, *SHIP TO*, *PO NO.*, *PO LINE NO.* and
*QTY* are extracted and printed for debugging. When the EDI contains the
same information, these values are compared and reported as matches or
mismatches in the JSON output.

The parser and validator emit `[DEBUG]` messages at key steps so you can
trace file loading and comparison logic when troubleshooting.

## Notes

Image, PDF and QR parsing requires `pdf2image`, `Pillow` and `pyzbar` to
be installed. These libraries are not included by default. When they are
missing the parser will log a debug message and return empty results
instead of raising an exception, so PDF or image labels simply won't be
parsed.
If you deploy on AWS Lambda, add the Poppler utilities (e.g. via an
Lambda layer) and set the environment variable `POPPLER_PATH` to the
directory containing `pdftoppm`. For example Poppler is often installed
under `/opt/bin`, so you can set `POPPLER_PATH=/opt/bin` or add that
directory to `PATH` so `pdf2image` can locate the binaries.

The EDI parser tolerates formatted files that contain line breaks between
segments, so the input may include or omit newlines after each `~` or `'
` character.

The X12 parser also reads purchase order numbers from `PRF` segments,
line items via `LIN` with `SN1` for quantities, and pack information
from `HL` loops that contain `SN1` and `MAN` segments.

Each QR block is checked against the EDI data. The validator compares
`asn_number`, `po_number`, `po_line_number`, `part_number` and the
quantity of each label with the corresponding pack or line item.
Line item quantities are additionally summed across labels. A total is
reported as a `match` only when this sum equals the quantity from the EDI
*and* every pack's quantity matched individually. The validator also
verifies that each line item defined in the EDI file appears on at least
one label with the same PO line and part number.

If any mismatches are found, the validator sets `success` to `false` and
adds human readable messages to an `errors` list in the JSON output so
the user can easily identify the problem fields.
When the overall quantity for a PO line matches the EDI value but one or
more individual pack quantities differ, the validator reports a total
mismatch with a message indicating that packs had conflicting quantities.

## AWS Lambda usage

To run validation automatically when files are uploaded to Amazon S3,
deploy the function `asn_validator.lambda_function.lambda_handler` as an
AWS Lambda triggered by an S3 "Object Created" event for the `edi/`
prefix. When an EDI file is uploaded, the handler looks for a label file
in a sibling `labels/` directory relative to the uploaded EDI file. For
example, if the EDI key is
`59366/2025/06/26/SH0433920/edi/SH0433920.txt` the handler searches for
`59366/2025/06/26/SH0433920/labels/SH0433920.pdf`. If the label does not
yet exist, the function returns a message indicating it is waiting for the
label. Once both files are present, they are downloaded, validated and
the JSON result is printed to the logs which are viewable in CloudWatch.
