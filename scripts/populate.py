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
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

import yaml
from pydantic import ValidationError

from gw2_data import api, llm, resolver, sorter, terminal, wiki
from gw2_data.cache import CacheClient
from gw2_data.config import get_settings
from gw2_data.exceptions import APIError, ExtractionError, MultipleItemMatchError, WikiError
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
        terminal.warning(f"Skipping {item_id}: file already exists (use --overwrite to replace)")
        return

    item_data_api = api.get_item(item_id, cache=cache)
    item_name = item_data_api["name"]
    terminal.section_header(f"Item: {item_name} (ID: {item_id})")

    is_basic_ingredient = (
        item_data_api["type"] == "CraftingMaterial"
        and item_data_api.get("description") == "Ingredient"
    )

    if is_basic_ingredient:
        terminal.info("Basic ingredient - skipping wiki/LLM extraction")
        acquisitions = []
        overall_confidence = 1.0
        entry_confidences: list[float] = []
        notes = None
    else:
        wiki_html = wiki.get_page_html(item_name, cache=cache)
        wiki_url = f"https://wiki.guildwars2.com/wiki/{item_name.replace(' ', '_')}"
        terminal.debug(f"Wiki page: {len(wiki_html):,} chars")
        terminal.info(f"  {terminal.link(wiki_url, 'View on Wiki')}")

        result = llm.extract_entries(
            item_id, item_name, wiki_html, item_data_api, cache=cache, model=model
        )
        overall_confidence = result.overall_confidence
        entry_confidences = result.entry_confidences
        notes = result.notes

        _print_extraction_summary(result.entries, overall_confidence, entry_confidences, notes)

        terminal.subsection("Classifying and resolving acquisitions")
        item_name_index = api.load_item_name_index()
        currency_name_index = api.load_currency_name_index()
        gathering_node_index = api.load_gathering_node_index()
        acquisitions = resolver.classify_and_resolve(
            result.entries,
            item_name_index,
            currency_name_index,
            gathering_node_index,
            strict=strict,
        )

    item_data = {
        "id": item_data_api["id"],
        "name": item_data_api["name"],
        "type": item_data_api["type"],
        "rarity": item_data_api["rarity"],
        "level": item_data_api["level"],
        "icon": item_data_api.get("icon"),
        "description": item_data_api.get("description"),
        "vendorValue": item_data_api.get("vendor_value"),
        "flags": item_data_api.get("flags", []),
        "wikiUrl": f"https://wiki.guildwars2.com/wiki/{item_name.replace(' ', '_')}",
        "lastUpdated": datetime.now(UTC).date().isoformat(),
        "acquisitions": acquisitions,
    }

    terminal.debug("Sorting acquisitions...")
    item_data["acquisitions"] = sorter.sort_acquisitions(item_data["acquisitions"])

    terminal.debug("Validating against schema...")
    try:
        validated = ItemFile.model_validate(item_data)
    except ValidationError as e:
        raise ExtractionError(f"Validation failed for item {item_id}: {e}") from e

    for acq in item_data.get("acquisitions", []):
        if acq.get("type") == "other":
            notes_text = (acq.get("metadata") or {}).get("notes", "no description")
            terminal.warning("'other' acquisition detected — unusual acquisition method")
            terminal.bullet(f'"{notes_text}"', indent=4)
            terminal.debug("  Consider whether a new acquisition type should be added.")

    yaml_content = validated.model_dump(by_alias=True, exclude_none=True)
    new_yaml = yaml.dump(yaml_content, sort_keys=False, allow_unicode=True)

    if output_path.exists():
        terminal.info("File already exists and will be overwritten.")

    if dry_run:
        if not output_path.exists():
            terminal.subsection(f"DRY RUN: Would write to {output_path}")
            terminal.code_block(new_yaml)
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w") as f:
        f.write(new_yaml)

    terminal.success(f"✓ Written to {output_path}")


def _print_extraction_summary(
    entries: list[dict],
    overall_confidence: float,
    entry_confidences: list[float],
    notes: str | None,
) -> None:
    terminal.subsection(
        f"Found {len(entries)} raw entry(ies)  |  Confidence: {overall_confidence:.0%}"
    )

    for i, entry in enumerate(entries):
        conf = entry_confidences[i] if i < len(entry_confidences) else 0.0
        wiki_section = entry.get("wikiSection", "unknown")
        wiki_subsection = entry.get("wikiSubsection")
        name = entry.get("name", "unknown")
        section_label = f"{wiki_section}/{wiki_subsection}" if wiki_subsection else wiki_section
        conf_str = f"[{conf:.0%}]"
        terminal.bullet(f"{conf_str} {section_label}: {name}", indent=2)

    if notes:
        terminal.debug(f"Notes: {notes}")


def _handle_multiple_matches_interactive(
    name: str, item_ids: list[int], cache: CacheClient
) -> None:
    terminal.error(f"Item name '{name}' matches multiple IDs")
    terminal.info("\nFetching item details to help you choose...\n")

    wiki_url = f"https://wiki.guildwars2.com/wiki/{name.replace(' ', '_')}"
    ids_param = ",".join(str(id) for id in item_ids)
    api_url = f"https://api.guildwars2.com/v2/items?ids={ids_param}"

    terminal.key_value("Wiki page", terminal.link(wiki_url))
    terminal.key_value("API comparison", terminal.link(api_url))

    terminal.subsection("Matching items")
    for item_id in item_ids:
        try:
            item_data = api.get_item(item_id, cache=cache)
            rarity = item_data.get("rarity", "Unknown")
            item_type = item_data.get("type", "Unknown")
            level = item_data.get("level", 0)
            terminal.bullet(
                f"ID {item_id}: {item_data['name']} ({rarity} {item_type}, Lv{level})",
                indent=2,
            )
        except Exception:
            terminal.bullet(f"ID {item_id}: (error fetching details)", indent=2)

    terminal.info("\nTo resolve this, either:")
    terminal.bullet("Add a manual override to data/index/item_name_overrides.yaml", indent=2)
    terminal.bullet("Use --item-id with the specific ID you want", indent=2)


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
    if acq_type == "container":
        return acq.get("containerName", "unknown")
    if acq_type == "salvage":
        return acq.get("requirementName", "unknown")
    if acq_type == "resource_node":
        return acq.get("nodeName", "unknown")
    if acq_type == "map_reward":
        return meta.get("rewardType", meta.get("regionName", "unknown reward"))
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
        terminal.success(f"Cache cleared{tag_str}")
        return

    try:
        if args.item_name:
            index = api.load_item_name_index()
            cleaned_name = api.clean_name(args.item_name)
            matches = index.get(cleaned_name)
            if not matches:
                terminal.error(f"No item found with name '{args.item_name}'")
                terminal.debug(f"Searched for cleaned name: '{cleaned_name}'")
                sys.exit(1)
            if len(matches) > 1:
                _handle_multiple_matches_interactive(args.item_name, matches, cache)
                sys.exit(1)
            item_id = matches[0]
            terminal.info(f"Resolved '{args.item_name}' to item ID {item_id}")
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

    except MultipleItemMatchError as e:
        _handle_multiple_matches_interactive(e.name, e.item_ids, cache)
        sys.exit(1)
    except (APIError, WikiError, ExtractionError, ValueError) as e:
        terminal.error(str(e))
        sys.exit(1)
    except Exception as e:
        terminal.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
