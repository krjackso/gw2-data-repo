"""
CLI script for populating acquisition data YAML files from GW2 API and wiki.

Fetches item metadata from the GW2 API, acquisition info from the wiki,
uses an LLM to extract structured data, validates against the schema, and
writes the result to data/acquisitions/{itemId}.yaml.
"""

import argparse
import sys
from pathlib import Path

import yaml
from pydantic import ValidationError

from gw2_data import api, llm, wiki
from gw2_data.cache import CacheClient
from gw2_data.config import get_settings
from gw2_data.exceptions import APIError, ExtractionError, WikiError
from gw2_data.models import AcquisitionFile


def populate_item(
    item_id: int, cache: CacheClient, overwrite: bool = False, dry_run: bool = False
) -> None:
    if item_id <= 0:
        raise ValueError(f"Item ID must be positive, got {item_id}")

    output_path = Path("data/acquisitions") / f"{item_id}.yaml"

    if output_path.exists() and not overwrite:
        print(f"Skipping {item_id}: file already exists (use --overwrite to replace)")
        return

    print(f"Fetching item data for ID {item_id}...")
    item_data = api.get_item(item_id, cache=cache)
    item_name = item_data["name"]
    print(f"Item: {item_name}")

    print(f"Fetching wiki page for {item_name}...")
    wiki_html = wiki.get_page_html(item_name, cache=cache)
    print(f"Wiki page fetched ({len(wiki_html)} chars)")

    print("Extracting acquisition data with LLM...")
    acquisition_data = llm.extract_acquisitions(
        item_id, item_name, wiki_html, item_data, cache=cache
    )

    print("Validating against schema...")
    try:
        validated = AcquisitionFile.model_validate(acquisition_data)
    except ValidationError as e:
        raise ExtractionError(f"Validation failed for item {item_id}: {e}") from e

    yaml_content = validated.model_dump(by_alias=True, exclude_none=True)

    if dry_run:
        print("\n--- DRY RUN: Would write to", output_path, "---")
        print(yaml.dump(yaml_content, sort_keys=False, allow_unicode=True))
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w") as f:
        yaml.dump(yaml_content, f, sort_keys=False, allow_unicode=True)

    print(f"✓ Written to {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Populate acquisition data for GW2 items"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--item-id", type=int, help="GW2 item ID (must be positive)")
    group.add_argument(
        "--item-name", type=str, help="GW2 item name (not yet supported)"
    )
    group.add_argument(
        "--clear-cache",
        nargs="*",
        metavar="TAG",
        help="Clear cache (optionally specify tags: api, wiki, llm)",
    )

    parser.add_argument(
        "--overwrite", action="store_true", help="Overwrite existing files"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Preview without writing files"
    )

    args = parser.parse_args()

    settings = get_settings()
    cache = CacheClient(settings.cache_dir)

    if args.clear_cache is not None:
        tags = args.clear_cache if args.clear_cache else None
        cache.clear_cache(tags)
        tag_str = f" ({', '.join(tags)})" if tags else " (all)"
        print(f"✓ Cache cleared{tag_str}")
        return

    try:
        if args.item_name:
            print("Error: --item-name is not yet implemented", file=sys.stderr)
            print("Please use --item-id instead", file=sys.stderr)
            sys.exit(1)
        else:
            item_id = args.item_id

        populate_item(item_id, cache, overwrite=args.overwrite, dry_run=args.dry_run)

    except (APIError, WikiError, ExtractionError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
