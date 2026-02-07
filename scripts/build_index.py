import argparse
import logging
import sys
import time
from collections import defaultdict
from pathlib import Path

import yaml

from gw2_data import api
from gw2_data.cache import CacheClient
from gw2_data.config import get_settings
from gw2_data.exceptions import APIError
from gw2_data.types import GW2Item

log = logging.getLogger(__name__)

INDEX_DIR = Path("data/index")
ITEM_NAMES_PATH = INDEX_DIR / "item_names.yaml"
CURRENCY_NAMES_PATH = INDEX_DIR / "currency_names.yaml"
BATCH_SIZE = 200
BATCH_DELAY = 0.1


class _IndexDumper(yaml.Dumper):
    pass


def _list_representer(dumper: yaml.Dumper, data: list) -> yaml.Node:
    return dumper.represent_sequence("tag:yaml.org,2002:seq", data, flow_style=True)


_IndexDumper.add_representer(list, _list_representer)


def _index_item(
    item: GW2Item,
    name_index: dict[str, list[int]],
    skipped_empty: list[int],
    cleaned_newlines: list[tuple[int, str]],
) -> None:
    name = item["name"]
    item_id = item["id"]

    if not name or not name.strip():
        skipped_empty.append(item_id)
        return

    if "\n" in name or "\r" in name:
        cleaned_newlines.append((item_id, repr(name)))

    name = api.clean_name(name)
    name_index[name].append(item_id)


def build_currency_index() -> None:
    import httpx

    from gw2_data.config import get_settings
    from gw2_data.exceptions import APIError

    print("Fetching all currencies from GW2 API...")
    settings = get_settings()

    try:
        response = httpx.get(
            "https://api.guildwars2.com/v2/currencies",
            params={"ids": "all"},
            timeout=settings.api_timeout,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise APIError(f"Failed to fetch currencies: HTTP {e.response.status_code}") from e
    except httpx.RequestError as e:
        raise APIError(f"Network error fetching currencies: {e}") from e

    currencies: list[dict] = response.json()
    print(f"Total currencies in GW2 API: {len(currencies)}")

    currency_index: dict[str, int] = {}
    skipped_empty = []
    for curr in currencies:
        name = curr["name"]
        if not name or not name.strip():
            skipped_empty.append(curr["id"])
            continue
        cleaned = api.clean_name(name)
        currency_index[cleaned] = curr["id"]

    if skipped_empty:
        print(f"Skipped {len(skipped_empty)} currency(ies) with empty names: {skipped_empty}")

    sorted_index = dict(sorted(currency_index.items()))

    INDEX_DIR.mkdir(parents=True, exist_ok=True)

    with CURRENCY_NAMES_PATH.open("w") as f:
        yaml.dump(sorted_index, f, allow_unicode=True, sort_keys=False)

    print(f"\nCurrency index written to {CURRENCY_NAMES_PATH}")
    print(f"  Total currencies indexed: {len(sorted_index)}")


def build_item_index(cache: CacheClient, *, force: bool = False) -> None:
    all_ids = api.get_all_item_ids()
    print(f"Total items in GW2 API: {len(all_ids):,}")

    batches = [all_ids[i : i + BATCH_SIZE] for i in range(0, len(all_ids), BATCH_SIZE)]
    total_batches = len(batches)
    print(f"Fetching in {total_batches} batches of up to {BATCH_SIZE}")

    name_index: dict[str, list[int]] = defaultdict(list)
    failed_batches: list[tuple[int, list[int]]] = []
    skipped_empty: list[int] = []
    cleaned_newlines: list[tuple[int, str]] = []
    fetched_count = 0

    for i, batch_ids in enumerate(batches):
        batch_num = i + 1
        from_cache = False
        try:
            result = api.get_items_bulk(batch_ids, cache, force=force)
            from_cache = result.from_cache
            for item in result.items:
                _index_item(item, name_index, skipped_empty, cleaned_newlines)
            fetched_count += len(result.items)
        except APIError as e:
            log.warning("Batch %d/%d failed: %s", batch_num, total_batches, e)
            failed_batches.append((batch_num, batch_ids))

        if batch_num % 10 == 0 or batch_num == total_batches:
            print(f"  Progress: {batch_num}/{total_batches} batches ({fetched_count:,} items)")

        if batch_num < total_batches and not from_cache:
            time.sleep(BATCH_DELAY)

    if failed_batches:
        print(f"\nRetrying {len(failed_batches)} failed batch(es)...")
        still_failed = []
        for batch_num, batch_ids in failed_batches:
            from_cache = False
            try:
                result = api.get_items_bulk(batch_ids, cache, force=force)
                from_cache = result.from_cache
                for item in result.items:
                    _index_item(item, name_index, skipped_empty, cleaned_newlines)
                fetched_count += len(result.items)
            except APIError as e:
                log.error("Batch %d retry failed: %s", batch_num, e)
                still_failed.append((batch_num, batch_ids))
            if not from_cache:
                time.sleep(BATCH_DELAY)

        if still_failed:
            failed_ids_count = sum(len(ids) for _, ids in still_failed)
            print(
                f"WARNING: {len(still_failed)} batch(es) failed permanently "
                f"({failed_ids_count} items missing)"
            )

    if skipped_empty:
        print(f"\nSkipped {len(skipped_empty)} item(s) with empty names: {skipped_empty}")

    if cleaned_newlines:
        print(f"\nCleaned newlines from {len(cleaned_newlines)} item name(s):")
        for item_id, raw_name in cleaned_newlines:
            print(f"  ID {item_id}: {raw_name}")

    sorted_index: dict[str, list[int]] = {}
    for name in sorted(name_index.keys()):
        sorted_index[name] = sorted(name_index[name])

    INDEX_DIR.mkdir(parents=True, exist_ok=True)

    with ITEM_NAMES_PATH.open("w") as f:
        yaml.dump(sorted_index, f, Dumper=_IndexDumper, allow_unicode=True, sort_keys=False)

    print(f"\nItem index written to {ITEM_NAMES_PATH}")
    print(f"  Unique names: {len(sorted_index):,}")
    print(f"  Total items indexed: {fetched_count:,}")
    duplicate_names = sum(1 for ids in sorted_index.values() if len(ids) > 1)
    if duplicate_names:
        print(f"  Names with multiple IDs: {duplicate_names:,}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build item or currency name-to-ID index from the GW2 API"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--items", action="store_true", help="Build item name index")
    group.add_argument("--currencies", action="store_true", help="Build currency name index")

    parser.add_argument(
        "--force", action="store_true", help="Ignore cache and re-fetch all items (items only)"
    )
    args = parser.parse_args()

    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(message)s",
    )

    try:
        if args.currencies:
            build_currency_index()
        else:
            cache = CacheClient(settings.cache_dir)
            build_item_index(cache, force=args.force)

    except APIError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
