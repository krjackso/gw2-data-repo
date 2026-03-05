"""
CLI script for populating vendor and location data.

Scans all item YAML files for unique vendor names, fetches their wiki
pages to extract location data, then fetches area pages to get waypoint
chat links. Writes two output files:

  data/vendors/vendors.yaml   - vendor name → wikiUrl + locations [{zone, area}]
  data/vendors/locations.yaml - zone → area → {wikiUrl, waypoint}
"""

import argparse
import logging
import sys
import time
from pathlib import Path
from urllib.parse import quote

import yaml

from gw2_data import terminal, wiki
from gw2_data.cache import CacheClient
from gw2_data.config import get_settings
from gw2_data.exceptions import WikiError
from gw2_data.models import LocationEntry, VendorEntry, VendorLocationRef, Waypoint
from gw2_data.vendor_scraper import (
    AreaRef,
    WaypointData,
    extract_area_waypoints,
    extract_vendor_locations,
)

_ITEMS_DIR = Path("data/items")
_OUTPUT_DIR = Path("data/vendors")
_VENDORS_FILE = _OUTPUT_DIR / "vendors.yaml"
_LOCATIONS_FILE = _OUTPUT_DIR / "locations.yaml"

_REQUEST_DELAY = 0.1

_WIKI_SAFE_CHARS = "/:@!$&'()*+,;="

log = logging.getLogger(__name__)


def _collect_vendor_names() -> list[str]:
    names: set[str] = set()
    for path in sorted(_ITEMS_DIR.glob("*.yaml")):
        with path.open() as f:
            item_data = yaml.safe_load(f)
        for acq in item_data.get("acquisitions", []):
            if acq.get("type") == "vendor":
                name = acq.get("vendorName")
                if name:
                    names.add(name)
    return sorted(names)


def _wiki_url_for(page_name: str) -> str:
    encoded = quote(page_name.replace(" ", "_"), safe=_WIKI_SAFE_CHARS)
    return f"https://wiki.guildwars2.com/wiki/{encoded}"


def _fetch_vendor_locations(vendor_name: str, cache: CacheClient) -> tuple[str, list[AreaRef]]:
    wiki_url = _wiki_url_for(vendor_name)
    try:
        html = wiki.get_page_html(vendor_name, cache=cache)
        time.sleep(_REQUEST_DELAY)
    except WikiError as e:
        log.warning("Could not fetch wiki page for vendor '%s': %s", vendor_name, e)
        return wiki_url, []

    locations = extract_vendor_locations(html)
    return wiki_url, locations


def _fetch_area_waypoints(area: AreaRef, cache: CacheClient) -> list[WaypointData]:
    try:
        html = wiki.get_page_html(area.wiki_page, cache=cache)
        time.sleep(_REQUEST_DELAY)
    except WikiError as e:
        log.warning("Could not fetch wiki page for area '%s': %s", area.wiki_page, e)
        return []
    return extract_area_waypoints(html)


def _area_key(area: AreaRef) -> tuple[str, str]:
    return (area.zone, area.name)


def _build_vendor_entry(wiki_url: str, areas: list[AreaRef]) -> VendorEntry:
    location_refs = [VendorLocationRef(zone=a.zone, area=a.name) for a in areas]
    return VendorEntry(wiki_url=wiki_url, locations=location_refs)


def _build_location_entry(area: AreaRef, waypoints: list[WaypointData]) -> LocationEntry:
    waypoint_models = [Waypoint(name=w.name, chat_link=w.chat_link) for w in waypoints]
    return LocationEntry(wiki_url=_wiki_url_for(area.wiki_page), waypoints=waypoint_models)


def _serialize_vendors(
    vendors: dict[str, VendorEntry],
) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for name, entry in sorted(vendors.items()):
        data = entry.model_dump(by_alias=True, exclude_none=True)
        result[name] = data
    return result


def _serialize_locations(
    locations: dict[tuple[str, str], LocationEntry],
) -> dict[str, dict[str, dict]]:
    result: dict[str, dict[str, dict]] = {}
    for (zone, area), entry in sorted(locations.items()):
        if zone not in result:
            result[zone] = {}
        result[zone][area] = entry.model_dump(by_alias=True, exclude_none=True)
    return result


def populate_vendors(
    vendor_filter: str | None,
    dry_run: bool,
    cache: CacheClient,
) -> None:
    terminal.section_header("Collecting vendor names from item files")
    all_vendor_names = _collect_vendor_names()
    if vendor_filter:
        matching = [n for n in all_vendor_names if n == vendor_filter]
        if not matching:
            terminal.error(f"Vendor '{vendor_filter}' not found in item files")
            sys.exit(1)
        all_vendor_names = matching
    terminal.info(f"Found {len(all_vendor_names)} unique vendor name(s)")

    vendors: dict[str, VendorEntry] = {}
    all_areas: dict[tuple[str, str], AreaRef] = {}

    terminal.section_header("Fetching vendor wiki pages")
    for i, vendor_name in enumerate(all_vendor_names):
        terminal.progress(i + 1, len(all_vendor_names), vendor_name)
        wiki_url, areas = _fetch_vendor_locations(vendor_name, cache)
        vendors[vendor_name] = _build_vendor_entry(wiki_url, areas)
        for area in areas:
            key = _area_key(area)
            if key not in all_areas:
                all_areas[key] = area

    terminal.section_header("Fetching area wiki pages for waypoints")
    locations: dict[tuple[str, str], LocationEntry] = {}
    unique_areas = list(all_areas.values())
    for i, area in enumerate(unique_areas):
        terminal.progress(i + 1, len(unique_areas), area.name)
        waypoints = _fetch_area_waypoints(area, cache)
        if waypoints:
            for wp in waypoints:
                terminal.debug(f"  → {wp.name} {wp.chat_link}")
        else:
            terminal.debug("  → no waypoints found")
        locations[_area_key(area)] = _build_location_entry(area, waypoints)

    vendors_data = _serialize_vendors(vendors)
    locations_data = _serialize_locations(locations)

    if dry_run:
        terminal.section_header("DRY RUN: vendors.yaml")
        terminal.code_block(yaml.dump(vendors_data, sort_keys=False, allow_unicode=True))
        terminal.section_header("DRY RUN: locations.yaml")
        terminal.code_block(yaml.dump(locations_data, sort_keys=False, allow_unicode=True))
        return

    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with _VENDORS_FILE.open("w") as f:
        yaml.dump(vendors_data, f, sort_keys=False, allow_unicode=True)
    terminal.success(f"Written {len(vendors_data)} vendors to {_VENDORS_FILE}")

    total_locations = sum(len(zones) for zones in locations_data.values())
    with _LOCATIONS_FILE.open("w") as f:
        yaml.dump(locations_data, f, sort_keys=False, allow_unicode=True)
    terminal.success(f"Written {total_locations} locations to {_LOCATIONS_FILE}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Populate vendor and location data from GW2 wiki")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview output without writing files",
    )
    parser.add_argument(
        "--vendor",
        type=str,
        default=None,
        help="Process only this vendor name",
    )
    parser.add_argument(
        "--clear-cache",
        nargs="*",
        metavar="TAG",
        help="Clear cache (optionally specify tags: api, wiki, llm)",
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

    populate_vendors(vendor_filter=args.vendor, dry_run=args.dry_run, cache=cache)


if __name__ == "__main__":
    main()
