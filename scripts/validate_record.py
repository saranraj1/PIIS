#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
from jsonschema import Draft202012Validator, FormatChecker

def main():
    p = argparse.ArgumentParser()
    p.add_argument("schema", type=Path)
    p.add_argument("record", type=Path, help="JSON object or JSON array")
    args = p.parse_args()
    schema = json.loads(args.schema.read_text())
    data = json.loads(args.record.read_text())
    records = data if isinstance(data, list) else [data]
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = []
    for i, record in enumerate(records):
        for error in validator.iter_errors(record):
            errors.append(f"record[{i}] {'.'.join(map(str, error.path))}: {error.message}")
    if errors:
        print("\n".join(errors))
        raise SystemExit(1)
    print(f"Validated {len(records)} record(s).")

if __name__ == "__main__":
    main()
