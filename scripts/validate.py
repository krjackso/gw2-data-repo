"""Validate all acquisition YAML files against the JSON Schema and Pydantic models."""

import json
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator
from pydantic import ValidationError as PydanticValidationError

from src.gw2_data.models import AcquisitionFile

REPO_ROOT = Path(__file__).parent.parent
SCHEMA_PATH = REPO_ROOT / "data" / "schema" / "acquisition.schema.json"
ACQUISITIONS_DIR = REPO_ROOT / "data" / "acquisitions"


def load_schema() -> dict:
    with open(SCHEMA_PATH) as f:
        return json.load(f)


def validate_file(filepath: Path, validator: Draft202012Validator) -> list[str]:
    errors: list[str] = []

    try:
        with open(filepath) as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        errors.append(f"YAML parse error: {e}")
        return errors

    if data is None:
        errors.append("File is empty")
        return errors

    for error in validator.iter_errors(data):
        path = " -> ".join(str(p) for p in error.absolute_path)
        location = f" at {path}" if path else ""
        errors.append(f"Schema: {error.message}{location}")

    try:
        AcquisitionFile.model_validate(data)
    except PydanticValidationError as e:
        for err in e.errors():
            loc = " -> ".join(str(part) for part in err["loc"])
            errors.append(f"Model: {err['msg']} at {loc}")

    return errors


def main() -> int:
    schema = load_schema()
    validator = Draft202012Validator(schema)

    yaml_files = sorted(ACQUISITIONS_DIR.glob("*.yaml"))

    if not yaml_files:
        print("No acquisition YAML files found. Nothing to validate.")
        return 0

    total_errors = 0
    for filepath in yaml_files:
        errors = validate_file(filepath, validator)
        if errors:
            print(f"\n{filepath.name}:")
            for error in errors:
                print(f"  - {error}")
            total_errors += len(errors)

    if total_errors:
        print(f"\n{total_errors} error(s) in {len(yaml_files)} file(s)")
        return 1

    print(f"All {len(yaml_files)} file(s) valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
