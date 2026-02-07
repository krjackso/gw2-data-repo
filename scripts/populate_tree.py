"""
Recursively populate item acquisition data by traversing the crafting tree.

Starting from a root item, populates that item's data, then discovers all
referenced item IDs in its requirements and populates those recursively.
Skips items that already have YAML files in data/items/.

Features:
- Cycle/duplicate detection to avoid infinite loops
- Configurable limit on number of new items to process per run
- Progress reporting with count of remaining unresolved items
- Clean Ctrl+C handling for safe interruption

IMPORTANT: --dry-run mode will only process the root item and will not
traverse its children, since no files are written to discover dependencies.
Use --dry-run only for previewing a single item's data.
"""

import argparse
import logging
import signal
import sys
from collections import deque
from pathlib import Path

import yaml

from gw2_data import api
from gw2_data.cache import CacheClient
from gw2_data.config import get_settings
from gw2_data.exceptions import APIError, ExtractionError, WikiError
from scripts.populate import populate_item

ITEMS_DIR = Path("data/items")

_interrupted = False


def _handle_sigint(signum: int, frame: object) -> None:
    global _interrupted
    if _interrupted:
        sys.exit(1)
    _interrupted = True
    print("\nInterrupt received — finishing current item, then stopping...")


def _get_existing_item_ids() -> set[int]:
    ids: set[int] = set()
    for path in ITEMS_DIR.glob("*.yaml"):
        try:
            ids.add(int(path.stem))
        except ValueError:
            continue
    return ids


def _analyze_item_file(item_id: int) -> tuple[set[int], list[str]]:
    path = ITEMS_DIR / f"{item_id}.yaml"
    if not path.exists():
        return set(), []

    data = yaml.safe_load(path.read_text())
    item_ids: set[int] = set()
    other_notes: list[str] = []

    for acq in data.get("acquisitions", []):
        if acq.get("type") == "other":
            notes = (acq.get("metadata") or {}).get("notes", "no description")
            other_notes.append(notes)

        for req in acq.get("requirements", []):
            if "itemId" in req:
                item_ids.add(req["itemId"])

    return item_ids, other_notes


def populate_tree(
    root_id: int,
    cache: CacheClient,
    limit: int | None = None,
    dry_run: bool = False,
    model: str | None = None,
) -> None:
    global _interrupted
    _interrupted = False

    existing = _get_existing_item_ids()

    queue: deque[int] = deque()
    seen: set[int] = set()
    queued_new = 0

    def enqueue(item_id: int) -> None:
        nonlocal queued_new
        if item_id not in seen:
            seen.add(item_id)
            queue.append(item_id)
            if item_id not in existing:
                queued_new += 1

    enqueue(root_id)

    processed = 0
    skipped = 0
    errors: list[tuple[int, str]] = []
    other_types: list[tuple[int, str]] = []

    while queue and not _interrupted:
        if limit is not None and processed >= limit:
            break

        item_id = queue.popleft()

        if item_id in existing:
            child_ids, notes_list = _analyze_item_file(item_id)
            new_children = 0
            for cid in child_ids:
                if cid not in seen:
                    enqueue(cid)
                    new_children += 1
            for notes in notes_list:
                other_types.append((item_id, notes))
            skipped += 1
            items_left_str = f" | {queued_new} new item(s) in queue" if queued_new else ""
            print(
                f"[skip] {item_id} already exists"
                f" — discovered {new_children} child(ren){items_left_str}"
            )
            continue

        queued_new -= 1
        budget_str = ""
        if limit is not None:
            budget_str = f" | budget: {processed + 1}/{limit}"
        print(
            f"\n{'=' * 60}\n"
            f"[{processed + 1}] Populating item {item_id}"
            f" | {queued_new} new item(s) queued{budget_str}\n"
            f"{'=' * 60}"
        )

        try:
            populate_item(item_id, cache, dry_run=dry_run, model=model)
            existing.add(item_id)
            processed += 1

            child_ids, notes_list = _analyze_item_file(item_id)
            new_children = 0
            for cid in child_ids:
                if cid not in seen:
                    enqueue(cid)
                    new_children += 1
            for notes in notes_list:
                other_types.append((item_id, notes))
            if new_children:
                print(f"Discovered {new_children} new item(s) in requirements")

        except KeyboardInterrupt:
            _interrupted = True
            print("\nInterrupt received — stopping after current item.")
            break
        except (APIError, WikiError, ExtractionError, ValueError) as e:
            errors.append((item_id, str(e)))
            print(f"Error processing item {item_id}: {e}", file=sys.stderr)
        except Exception as e:
            errors.append((item_id, str(e)))
            print(f"Unexpected error processing item {item_id}: {e}", file=sys.stderr)

    remaining_total = len(queue)

    print(f"\n{'=' * 60}")
    print("Tree traversal summary")
    print(f"{'=' * 60}")
    print(f"  New items populated: {processed}")
    print(f"  Existing items skipped: {skipped}")
    print(f"  Errors: {len(errors)}")
    print(f"  Items remaining in queue: {remaining_total} ({queued_new} new)")

    if other_types:
        print(f"\n⚠ Items with 'other' acquisition type ({len(other_types)}):")
        for oid, notes in other_types:
            print(f"  {oid}: {notes}")

    if errors:
        print("\nFailed items:")
        for eid, msg in errors:
            print(f"  {eid}: {msg}")

    if _interrupted:
        print("\nStopped early due to interrupt.")
    elif limit is not None and processed >= limit:
        print(f"\nStopped after reaching limit of {limit} new item(s).")

    if queued_new > 0:
        print(f"\nRe-run to continue processing {queued_new} remaining new item(s).")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Recursively populate item acquisition data by traversing the crafting tree"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--item-id", type=int, help="Root item ID to start traversal from")
    group.add_argument("--item-name", type=str, help="Root item name (resolved via index)")

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of new items to populate (default: unlimited)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview without writing files (NOTE: will not traverse children)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Override LLM model (e.g. claude-sonnet-4-5-20250929)",
    )

    args = parser.parse_args()

    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(message)s",
    )
    cache = CacheClient(settings.cache_dir)

    signal.signal(signal.SIGINT, _handle_sigint)

    try:
        if args.item_name:
            index = api.load_item_name_index()
            cleaned_name = api.clean_name(args.item_name)
            matches = index.get(cleaned_name)
            if not matches:
                print(f"Error: No item found with name '{args.item_name}'", file=sys.stderr)
                sys.exit(1)
            if len(matches) > 1:
                print(f"Multiple items match '{args.item_name}':", file=sys.stderr)
                for mid in matches:
                    print(f"  --item-id {mid}", file=sys.stderr)
                sys.exit(1)
            root_id = matches[0]
            print(f"Resolved '{args.item_name}' to item ID {root_id}")
        else:
            root_id = args.item_id

        populate_tree(root_id, cache, limit=args.limit, dry_run=args.dry_run, model=args.model)

    except KeyboardInterrupt:
        print("\nAborted.")
        sys.exit(1)


if __name__ == "__main__":
    main()
