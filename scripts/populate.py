"""
CLI script for populating item acquisition data.

Orchestrates the acquisition data pipeline:
1. Fetch item data from GW2 API
2. Fetch wiki page HTML
3. Extract acquisitions via LLM
4. Resolve item/currency names to IDs
5. Sort acquisitions deterministically
6. Validate against schema
7. Write to YAML file
"""

import argparse
import difflib
import logging
import sys
from pathlib import Path

import yaml
from pydantic import ValidationError

from gw2_data import api, llm, resolver, sorter, wiki
from gw2_data.cache import CacheClient
from gw2_data.config import get_settings
from gw2_data.exceptions import APIError, ExtractionError, WikiError
from gw2_data.models import ItemFile


def populate_item(
    item_id: int,
    cache: CacheClient,
    overwrite: bool = False,
    dry_run: bool = False,
    model: str | None = None,
    strict: bool = True,
) -> None:
    if item_id <= 0:
        raise ValueError(f"Item ID must be positive, got {item_id}")

    output_path = Path("data/items") / f"{item_id}.yaml"

    if output_path.exists() and not overwrite:
        print(f"Skipping {item_id}: file already exists (use --overwrite to replace)")
        return

    item_data = api.get_item(item_id, cache=cache)
    item_name = item_data["name"]
    print(f"Item: {item_name} (ID: {item_id})")

    wiki_html = wiki.get_page_html(item_name, cache=cache)
    print(f"Wiki page: {len(wiki_html):,} chars")

    result = llm.extract_acquisitions(
        item_id, item_name, wiki_html, item_data, cache=cache, model=model
    )

    _print_extraction_summary(result)

    print("Resolving item/currency names to IDs...")
    item_name_index = api.load_item_name_index()
    currency_name_index = api.load_currency_name_index()
    result.item_data["acquisitions"] = resolver.resolve_requirements(
        result.item_data["acquisitions"], item_name_index, currency_name_index, strict=strict
    )

    print("Sorting acquisitions...")
    result.item_data["acquisitions"] = sorter.sort_acquisitions(result.item_data["acquisitions"])

    print("Validating against schema...")
    try:
        validated = ItemFile.model_validate(result.item_data)
    except ValidationError as e:
        raise ExtractionError(f"Validation failed for item {item_id}: {e}") from e

    for acq in result.item_data.get("acquisitions", []):
        if acq.get("type") == "other":
            notes = (acq.get("metadata") or {}).get("notes", "no description")
            print(
                f"\n⚠ 'other' acquisition detected — unusual acquisition method:\n"
                f'  "{notes}"\n'
                f"  Consider whether a new acquisition type should be added."
            )

    yaml_content = validated.model_dump(by_alias=True, exclude_none=True)
    new_yaml = yaml.dump(yaml_content, sort_keys=False, allow_unicode=True)

    if output_path.exists():
        old_yaml = output_path.read_text()
        diff = difflib.unified_diff(
            old_yaml.splitlines(keepends=True),
            new_yaml.splitlines(keepends=True),
            fromfile=f"a/{output_path}",
            tofile=f"b/{output_path}",
        )
        diff_text = "".join(diff)
        if diff_text:
            print(f"\n--- Diff from existing {output_path} ---")
            print(diff_text)
        else:
            print("\nNo changes from existing file.")

    if dry_run:
        if not output_path.exists():
            print("\n--- DRY RUN: Would write to", output_path, "---")
            print(new_yaml)
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w") as f:
        f.write(new_yaml)

    print(f"Written to {output_path}")


def _print_extraction_summary(result: llm.ExtractionResult) -> None:
    acqs = result.item_data.get("acquisitions", [])
    print(
        f"\nFound {len(acqs)} acquisition(s)  |  "
        f"Overall confidence: {result.overall_confidence:.0%}"
    )

    for i, acq in enumerate(acqs):
        conf = result.acquisition_confidences[i] if i < len(result.acquisition_confidences) else 0.0
        acq_type = acq.get("type", "unknown")
        label = _acquisition_label(acq)
        print(f"  [{conf:.0%}] {acq_type}: {label}")

    if result.notes:
        print(f"\nNotes: {result.notes}")


def _acquisition_label(acq: dict) -> str:
    meta = acq.get("metadata", {}) or {}
    acq_type = acq.get("type", "")
    if acq_type == "vendor":
        return acq.get("vendorName", "unknown vendor")
    if acq_type in ("crafting", "mystic_forge"):
        reqs = acq.get("requirements", [])
        ingredients = [r.get("requirementName", "?") for r in reqs]
        return ", ".join(ingredients[:4]) + ("..." if len(ingredients) > 4 else "")
    if acq_type == "achievement":
        return acq.get("achievementName", "unknown achievement")
    if acq_type in ("wvw_reward", "pvp_reward"):
        return acq.get("trackName", "unknown track")
    if acq_type == "wizards_vault":
        reqs = acq.get("requirements", [])
        cost = reqs[0].get("quantity", "?") if reqs else "?"
        return f"{cost} Astral Acclaim"
    if acq_type in ("container", "salvage"):
        return acq.get("requirementName", "unknown")
    if acq_type == "map_reward":
        return meta.get("rewardType", meta.get("regionName", "unknown reward"))
    if acq_type == "story":
        return meta.get("storyChapter", meta.get("expansion", "unknown story"))
    if acq_type == "other":
        return meta.get("notes", "no description")
    return ""


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Populate item data with acquisitions for GW2 items"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--item-id", type=int, help="GW2 item ID (must be positive)")
    group.add_argument("--item-name", type=str, help="GW2 item name (resolved via index)")
    group.add_argument(
        "--clear-cache",
        nargs="*",
        metavar="TAG",
        help="Clear cache (optionally specify tags: api, wiki, llm)",
    )

    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing files")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing files")
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Override LLM model (e.g. claude-sonnet-4-5-20250929)",
    )

    strict_group = parser.add_mutually_exclusive_group()
    strict_group.add_argument(
        "--strict",
        dest="strict",
        action="store_true",
        default=True,
        help="Fail on unresolvable requirements (default)",
    )
    strict_group.add_argument(
        "--no-strict",
        dest="strict",
        action="store_false",
        help="Skip acquisitions with unresolvable requirements instead of failing",
    )

    args = parser.parse_args()

    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(message)s",
    )
    cache = CacheClient(settings.cache_dir)

    if args.clear_cache is not None:
        tags = args.clear_cache if args.clear_cache else None
        cache.clear_cache(tags)
        tag_str = f" ({', '.join(tags)})" if tags else " (all)"
        print(f"Cache cleared{tag_str}")
        return

    try:
        if args.item_name:
            index = api.load_item_name_index()
            cleaned_name = api.clean_name(args.item_name)
            matches = index.get(cleaned_name)
            if not matches:
                print(f"Error: No item found with name '{args.item_name}'", file=sys.stderr)
                print(f"Searched for cleaned name: '{cleaned_name}'", file=sys.stderr)
                sys.exit(1)
            if len(matches) > 1:
                print(f"Multiple items match '{args.item_name}':", file=sys.stderr)
                for mid in matches:
                    print(f"  --item-id {mid}", file=sys.stderr)
                sys.exit(1)
            item_id = matches[0]
            print(f"Resolved '{args.item_name}' to item ID {item_id}")
        else:
            item_id = args.item_id

        populate_item(
            item_id,
            cache,
            overwrite=args.overwrite,
            dry_run=args.dry_run,
            model=args.model,
            strict=args.strict,
        )

    except (APIError, WikiError, ExtractionError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
