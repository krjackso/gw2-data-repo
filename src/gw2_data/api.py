"""
GW2 API client for fetching item and recipe data.

Wraps the official GW2 API (api.guildwars2.com/v2) with caching and
error handling. All responses are cached indefinitely since game data
rarely changes.
"""

import logging
import re
from pathlib import Path

import httpx
import yaml

from gw2_data.cache import CacheClient
from gw2_data.config import get_settings
from gw2_data.exceptions import APIError
from gw2_data.types import BulkResult, GW2Item, GW2Recipe

log = logging.getLogger(__name__)

_BASE_URL = "https://api.guildwars2.com/v2"


def get_item(item_id: int, cache: CacheClient) -> GW2Item:
    if item_id <= 0:
        raise APIError(f"Invalid item ID: {item_id}")

    cached = cache.get_api_item(item_id)
    if cached is not None:
        log.info("Item %d: using cached API data", item_id)
        return cached

    log.info("Item %d: fetching from GW2 API", item_id)
    settings = get_settings()
    try:
        response = httpx.get(f"{_BASE_URL}/items/{item_id}", timeout=settings.api_timeout)
        response.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise APIError(f"Failed to fetch item {item_id}: HTTP {e.response.status_code}") from e
    except httpx.RequestError as e:
        raise APIError(f"Network error fetching item {item_id}: {e}") from e

    data: GW2Item = response.json()
    cache.set_api_item(item_id, data)
    return data


def get_recipe(recipe_id: int, cache: CacheClient) -> GW2Recipe:
    if recipe_id <= 0:
        raise APIError(f"Invalid recipe ID: {recipe_id}")

    cached = cache.get_api_recipe(recipe_id)
    if cached is not None:
        log.info("Recipe %d: using cached API data", recipe_id)
        return cached

    log.info("Recipe %d: fetching from GW2 API", recipe_id)
    settings = get_settings()
    try:
        response = httpx.get(f"{_BASE_URL}/recipes/{recipe_id}", timeout=settings.api_timeout)
        response.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise APIError(f"Failed to fetch recipe {recipe_id}: HTTP {e.response.status_code}") from e
    except httpx.RequestError as e:
        raise APIError(f"Network error fetching recipe {recipe_id}: {e}") from e

    data: GW2Recipe = response.json()
    cache.set_api_recipe(recipe_id, data)
    return data


def search_recipes_by_output(item_id: int, cache: CacheClient) -> list[int]:
    if item_id <= 0:
        raise APIError(f"Invalid item ID: {item_id}")

    cached = cache.get_api_recipes_search(item_id)
    if cached is not None:
        log.info("Recipe search for item %d: using cached data", item_id)
        return cached

    log.info("Recipe search for item %d: fetching from GW2 API", item_id)
    settings = get_settings()
    try:
        response = httpx.get(
            f"{_BASE_URL}/recipes/search",
            params={"output": item_id},
            timeout=settings.api_timeout,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise APIError(
            f"Failed to search recipes for item {item_id}: HTTP {e.response.status_code}"
        ) from e
    except httpx.RequestError as e:
        raise APIError(f"Network error searching recipes for item {item_id}: {e}") from e

    recipe_ids: list[int] = response.json()
    cache.set_api_recipes_search(item_id, recipe_ids)
    return recipe_ids


def get_all_item_ids() -> list[int]:
    log.info("Fetching all item IDs from GW2 API")
    settings = get_settings()
    try:
        response = httpx.get(f"{_BASE_URL}/items", timeout=settings.api_timeout)
        response.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise APIError(f"Failed to fetch item IDs: HTTP {e.response.status_code}") from e
    except httpx.RequestError as e:
        raise APIError(f"Network error fetching item IDs: {e}") from e

    item_ids: list[int] = response.json()
    log.info("Got %d item IDs", len(item_ids))
    return item_ids


def get_items_bulk(item_ids: list[int], cache: CacheClient, *, force: bool = False) -> BulkResult:
    if not item_ids:
        return BulkResult(items=[], from_cache=True)
    if len(item_ids) > 200:
        raise APIError(f"Bulk fetch limited to 200 items, got {len(item_ids)}")

    if not force:
        cached_items: list[GW2Item] = []
        all_cached = True
        for item_id in item_ids:
            cached = cache.get_api_item(item_id)
            if cached is not None:
                cached_items.append(cached)
            else:
                all_cached = False
                break
        if all_cached:
            log.debug("Batch of %d items: all cached", len(item_ids))
            return BulkResult(items=cached_items, from_cache=True)

    log.debug("Batch of %d items: fetching from API", len(item_ids))
    settings = get_settings()
    ids_param = ",".join(str(i) for i in item_ids)
    try:
        response = httpx.get(
            f"{_BASE_URL}/items", params={"ids": ids_param}, timeout=settings.api_timeout
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise APIError(f"Failed to fetch item batch: HTTP {e.response.status_code}") from e
    except httpx.RequestError as e:
        raise APIError(f"Network error fetching item batch: {e}") from e

    items: list[GW2Item] = response.json()
    for item in items:
        cache.set_api_item(item["id"], item)
    return BulkResult(items=items, from_cache=False)


def clean_name(name: str) -> str:
    return re.sub(r"\s+", " ", name.replace("\n", " ").replace("\r", " ")).strip()


def load_item_name_index() -> dict[str, list[int]]:
    index_path = Path("data/index/item_names.yaml")
    override_path = Path("data/index/item_name_overrides.yaml")

    if not index_path.exists():
        raise APIError(
            f"Item name index not found at {index_path}. "
            "Run 'uv run python -m scripts.build_index' first."
        )

    with index_path.open() as f:
        index: dict[str, list[int]] = yaml.safe_load(f)

    if override_path.exists():
        with override_path.open() as f:
            overrides: dict[str, int] = yaml.safe_load(f) or {}
        for name, item_id in overrides.items():
            index[name] = [item_id]

    return index


def load_currency_name_index() -> dict[str, int]:
    index_path = Path("data/index/currency_names.yaml")
    override_path = Path("data/index/currency_name_overrides.yaml")

    if not index_path.exists():
        raise APIError(
            f"Currency name index not found at {index_path}. "
            "Run 'uv run python -m scripts.build_index --currencies' first."
        )

    with index_path.open() as f:
        index: dict[str, int] = yaml.safe_load(f)

    if override_path.exists():
        with override_path.open() as f:
            overrides: dict[str, int] = yaml.safe_load(f) or {}
        index.update(overrides)

    return index


def resolve_item_name_to_id(name: str, index: dict[str, list[int]]) -> int:
    cleaned = clean_name(name)
    matches = index.get(cleaned)
    if not matches:
        raise APIError(f"Item name '{name}' not found in index (cleaned: '{cleaned}')")
    if len(matches) > 1:
        raise APIError(
            f"Item name '{name}' matches multiple IDs: {matches}. Cannot resolve automatically."
        )
    return matches[0]


def resolve_currency_name_to_id(name: str, index: dict[str, int]) -> int:
    cleaned = clean_name(name)
    currency_id = index.get(cleaned)
    if currency_id is None:
        raise APIError(f"Currency name '{name}' not found in index (cleaned: '{cleaned}')")
    return currency_id
