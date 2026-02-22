"""
Recursively populate item acquisition data by traversing the crafting tree.

Starting from a root item, populates that item's data, then discovers all
referenced item IDs in its requirements and populates those recursively.
Skips items that already have YAML files in data/items/ (unless --force is used).

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
import subprocess
import sys
import threading
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import yaml

from gw2_data import api, terminal
from gw2_data.cache import CacheClient
from gw2_data.config import get_settings
from gw2_data.exceptions import APIError, ExtractionError, WikiError
from scripts.populate import populate_item

ITEMS_DIR = Path("data/items")

_interrupted = False
_state_lock = threading.Lock()


def _handle_sigint(signum: int, frame: object) -> None:
    global _interrupted
    if _interrupted:
        sys.exit(1)
    _interrupted = True
    terminal.warning("Interrupt received — finishing current item, then stopping...")


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


def _play_completion_sound() -> None:
    try:
        subprocess.run(
            ["afplay", "/System/Library/Sounds/Glass.aiff"],
            check=False,
            capture_output=True,
        )
    except Exception:
        pass


def _display_error_details(item_id: int, error_msg: str, cache: CacheClient) -> None:
    terminal.bullet(f"{item_id}: {error_msg}", indent=2, symbol="✗")
    try:
        item = api.get_item(item_id, cache)
        item_name = item.get("name", "Unknown")
        wiki_url = f"https://wiki.guildwars2.com/wiki/{item_name.replace(' ', '_')}"
        terminal.info(f"    Wiki: {wiki_url}")
    except Exception:
        pass
    terminal.info(f"    Debug with: uv run python -m scripts.populate --item-id {item_id}")


def populate_tree(
    root_ids: list[int],
    cache: CacheClient,
    limit: int | None = None,
    dry_run: bool = False,
    model: str | None = None,
    force: bool = False,
    workers: int = 1,
    show_errors: bool = True,
) -> list[tuple[int, str]]:
    global _interrupted
    _interrupted = False

    existing = set[int]() if force else _get_existing_item_ids()

    queue: deque[int] = deque()
    seen: set[int] = set()
    queued_new = 0

    def enqueue(item_id: int) -> None:
        nonlocal queued_new
        with _state_lock:
            if item_id not in seen:
                seen.add(item_id)
                queue.append(item_id)
                if item_id not in existing:
                    queued_new += 1

    def _skip_existing() -> None:
        nonlocal skipped
        while queue and queue[0] in existing:
            item_id = queue.popleft()
            child_ids, notes_list = _analyze_item_file(item_id)
            for cid in child_ids:
                if cid not in seen:
                    enqueue(cid)
            for notes in notes_list:
                other_types.append((item_id, notes))
            skipped += 1

    def _drain_batch() -> list[int]:
        nonlocal queued_new, skipped
        batch: list[int] = []
        remaining = (limit - processed) if limit is not None else None
        while queue and len(batch) < workers:
            if remaining is not None and len(batch) >= remaining:
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
                continue
            queued_new -= 1
            batch.append(item_id)
        return batch

    def _handle_result(item_id: int) -> None:
        nonlocal processed
        child_ids, notes_list = _analyze_item_file(item_id)
        new_children = 0
        for cid in child_ids:
            if cid not in seen:
                enqueue(cid)
                new_children += 1
        with _state_lock:
            existing.add(item_id)
            processed += 1
            for notes in notes_list:
                other_types.append((item_id, notes))
        if new_children:
            terminal.debug(f"  → Discovered {new_children} new requirement(s)")

    for root_id in root_ids:
        enqueue(root_id)

    processed = 0
    skipped = 0
    errors: list[tuple[int, str]] = []
    other_types: list[tuple[int, str]] = []

    def _run_item(iid: int) -> None:
        with terminal.buffered():
            populate_item(iid, cache, overwrite=force, dry_run=dry_run, model=model)

    _skip_existing()

    while queue and not _interrupted:
        if limit is not None and processed >= limit:
            break

        batch = _drain_batch()
        if not batch:
            break

        with _state_lock:
            current_processed = processed
            current_queued = queued_new
        batch_ids = ", ".join(str(i) for i in batch)
        if limit is not None:
            terminal.progress(
                current_processed + len(batch),
                limit,
                f"Processing {batch_ids} ({current_queued} queued)",
            )
        else:
            terminal.info(
                f"\n[{current_processed + 1}] Processing {batch_ids} ({current_queued} queued)"
            )

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(_run_item, item_id): item_id for item_id in batch}
            for future in as_completed(futures):
                item_id = futures[future]
                try:
                    future.result()
                    _handle_result(item_id)
                except (APIError, WikiError, ExtractionError, ValueError) as e:
                    errors.append((item_id, str(e)))
                    terminal.error(f"Failed to process item {item_id}: {e}")
                except Exception as e:
                    errors.append((item_id, str(e)))
                    terminal.error(f"Unexpected error processing item {item_id}: {e}")

        _skip_existing()

    remaining_total = len(queue)

    terminal.section_header("Tree Traversal Summary")
    terminal.key_value("New items populated", str(processed))
    terminal.key_value("Existing items skipped", str(skipped))
    terminal.key_value("Errors", str(len(errors)))
    terminal.key_value("Items remaining in queue", f"{remaining_total} ({queued_new} new)")

    if other_types:
        terminal.warning(f"Items with 'other' acquisition type ({len(other_types)})")
        for oid, notes in other_types:
            terminal.bullet(f"{oid}: {notes}", indent=2)

    if errors and show_errors:
        terminal.subsection("Failed items")
        for eid, msg in errors:
            _display_error_details(eid, msg, cache)

    if _interrupted:
        terminal.warning("Stopped early due to interrupt.")
    elif limit is not None and processed >= limit:
        terminal.info(f"Stopped after reaching limit of {limit} new item(s).")

    if queued_new > 0:
        terminal.info(f"\nRe-run to continue processing {queued_new} remaining new item(s).")

    _play_completion_sound()

    return errors


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Recursively populate item acquisition data by traversing the crafting tree"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--item-id",
        type=str,
        help="Root item ID(s) to start traversal from (comma-separated for multiple roots)",
    )
    group.add_argument("--item-name", type=str, help="Root item name (resolved via index)")

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of new items to populate (default: unlimited)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-populate all items in the tree, even if YAML files already exist",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview without writing files (NOTE: will not traverse children)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Number of items to process concurrently (default: 4)",
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
        root_ids: list[int] = []

        if args.item_name:
            index = api.load_item_name_index()
            cleaned_name = api.clean_name(args.item_name)
            matches = index.get(cleaned_name)
            if not matches:
                terminal.error(f"No item found with name '{args.item_name}'")
                sys.exit(1)
            if len(matches) > 1:
                terminal.error(f"Multiple items match '{args.item_name}':")
                for mid in matches:
                    terminal.bullet(f"--item-id {mid}", indent=2)
                sys.exit(1)
            root_ids = [matches[0]]
            terminal.info(f"Resolved '{args.item_name}' to item ID {root_ids[0]}\n")
        else:
            id_strings = [s.strip() for s in args.item_id.split(",")]
            try:
                root_ids = [int(s) for s in id_strings]
            except ValueError as e:
                terminal.error(f"Invalid item ID format: {e}")
                sys.exit(1)

        if len(root_ids) > 1:
            ids_str = ", ".join(str(r) for r in root_ids)
            terminal.info(f"Processing {len(root_ids)} root items: {ids_str}\n")

        populate_tree(
            root_ids,
            cache,
            limit=args.limit,
            dry_run=args.dry_run,
            model=args.model,
            force=args.force,
            workers=args.workers,
        )

    except KeyboardInterrupt:
        terminal.warning("\nAborted.")
        sys.exit(1)


if __name__ == "__main__":
    main()
