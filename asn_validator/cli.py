import argparse
import json
from .validator import validate


def main():
    parser = argparse.ArgumentParser(description="Validate ASN label against EDI")
    parser.add_argument("label", help="Path to label PDF or image")
    parser.add_argument("edi", help="Path to EDI file (X12 or EDIFACT)")
    args = parser.parse_args()
    result = validate(args.label, args.edi)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
