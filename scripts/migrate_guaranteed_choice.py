"""
Migration script to move guaranteed and choice fields from metadata to top-level.

Processes all YAML files in data/items/ and:
1. Moves metadata.guaranteed → top-level guaranteed
2. Moves metadata.choice → top-level choice
3. Preserves all other fields and formatting
4. Validates output against schema
"""

import sys
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from gw2_data.models import ItemFile
from gw2_data.sorter import sort_acquisitions


def migrate_acquisition(acq: dict[str, Any]) -> dict[str, Any]:
    metadata = acq.get("metadata", {})
    if not isinstance(metadata, dict):
        return acq

    migrated = {**acq}
    new_metadata = {**metadata}

    if "guaranteed" in metadata:
        migrated["guaranteed"] = metadata["guaranteed"]
        del new_metadata["guaranteed"]

    if "choice" in metadata:
        migrated["choice"] = metadata["choice"]
        del new_metadata["choice"]

    if new_metadata:
        migrated["metadata"] = new_metadata
    elif "metadata" in migrated:
        del migrated["metadata"]

    return migrated


def migrate_file(file_path: Path, dry_run: bool = False) -> bool:
    with open(file_path) as f:
        data = yaml.safe_load(f)

    if not data or "acquisitions" not in data:
        return False

    migrated = False
    new_acquisitions = []

    for acq in data["acquisitions"]:
        metadata = acq.get("metadata", {})
        has_fields = isinstance(metadata, dict) and (
            "guaranteed" in metadata or "choice" in metadata
        )

        if has_fields:
            migrated = True
            new_acquisitions.append(migrate_acquisition(acq))
        else:
            new_acquisitions.append(acq)

    if not migrated:
        return False

    data["acquisitions"] = sort_acquisitions(new_acquisitions)

    ItemFile.model_validate(data)

    if not dry_run:
        with open(file_path, "w") as f:
            yaml.dump(
                data,
                f,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
                width=float("inf"),
            )

    return True


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Migrate guaranteed and choice fields from metadata to top-level"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be migrated without writing files",
    )
    args = parser.parse_args()

    data_dir = Path(__file__).parent.parent / "data" / "items"
    yaml_files = sorted(data_dir.glob("*.yaml"))

    migrated_count = 0
    total_count = len(yaml_files)

    print(f"Processing {total_count} YAML files...")

    for file_path in yaml_files:
        try:
            if migrate_file(file_path, dry_run=args.dry_run):
                migrated_count += 1
                action = "Would migrate" if args.dry_run else "Migrated"
                print(f"{action}: {file_path.name}")
        except Exception as e:
            print(f"Error processing {file_path.name}: {e}")
            sys.exit(1)

    action = "would be migrated" if args.dry_run else "migrated"
    print(f"\n{migrated_count}/{total_count} files {action}")

    if args.dry_run and migrated_count > 0:
        print("\nRun without --dry-run to apply changes")


if __name__ == "__main__":
    main()
