"""
Migration script to backfill containerName on existing container acquisitions.

Reads all item YAML files, finds container acquisitions with itemId but no
containerName, looks up the item name from the GW2 API, and writes back the
updated YAML with containerName populated.
"""

import logging
from pathlib import Path

import yaml
from pydantic import ValidationError

from gw2_data import api, terminal
from gw2_data.cache import CacheClient
from gw2_data.config import get_settings
from gw2_data.exceptions import APIError
from gw2_data.models import ItemFile

log = logging.getLogger(__name__)


def migrate_file(file_path: Path, cache: CacheClient, dry_run: bool) -> bool:
    with file_path.open() as f:
        data = yaml.safe_load(f)

    acquisitions = data.get("acquisitions", [])
    modified = False

    for acq in acquisitions:
        if acq.get("type") == "container":
            if "itemId" in acq and "containerName" not in acq:
                item_id = acq["itemId"]
                try:
                    item_data = api.get_item(item_id, cache)
                    container_name = item_data["name"]
                    acq["containerName"] = container_name
                    modified = True
                    terminal.debug(
                        f"  {file_path.name}: Added containerName='{container_name}' "
                        f"for itemId={item_id}"
                    )
                except APIError as e:
                    terminal.warning(f"  {file_path.name}: Failed to resolve itemId={item_id}: {e}")
                    continue

    if not modified:
        return False

    try:
        validated = ItemFile.model_validate(data)
    except ValidationError as e:
        terminal.error(f"  {file_path.name}: Validation failed after migration: {e}")
        return False

    yaml_content = validated.model_dump(by_alias=True, exclude_none=True)
    new_yaml = yaml.dump(yaml_content, sort_keys=False, allow_unicode=True)

    if dry_run:
        terminal.info(f"  {file_path.name}: Would update (dry run)")
        return True

    with file_path.open("w") as f:
        f.write(new_yaml)

    return True


def migrate_all_files(dry_run: bool = False) -> None:
    settings = get_settings()
    cache = CacheClient(settings.cache_dir)

    items_dir = Path("data/items")
    if not items_dir.exists():
        terminal.error(f"Items directory not found: {items_dir}")
        return

    yaml_files = sorted(items_dir.glob("*.yaml"))
    terminal.subsection(f"Migrating {len(yaml_files)} YAML files...")

    migrated_count = 0
    for file_path in yaml_files:
        try:
            if migrate_file(file_path, cache, dry_run):
                migrated_count += 1
        except Exception as e:
            terminal.error(f"  {file_path.name}: Unexpected error: {e}")
            continue

    terminal.success(
        f"\n✓ Migration complete: {migrated_count} file(s) updated "
        f"({'dry run' if dry_run else 'written'})"
    )


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Backfill containerName on existing container acquisitions"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be changed without writing files",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    migrate_all_files(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
