"""
GW2 API client for fetching item and recipe data.

Wraps the official GW2 API (api.guildwars2.com/v2) with caching and
error handling. All responses are cached indefinitely since game data
rarely changes.
"""

import logging

import httpx

from gw2_data.cache import CacheClient
from gw2_data.config import get_settings
from gw2_data.exceptions import APIError
from gw2_data.types import GW2Item, GW2Recipe

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
