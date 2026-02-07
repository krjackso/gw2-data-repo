"""
Cache layer for GW2 API and wiki data using diskcache.

Provides persistent caching across script invocations to minimize
API calls, wiki fetches, and LLM processing costs. Cache is stored
in a configurable directory and organized by tags (api, wiki, llm)
for selective clearing.
"""

from pathlib import Path

from diskcache import Cache as DiskCache

from gw2_data.types import GW2Item, GW2Recipe


class CacheClient:
    def __init__(self, cache_dir: Path):
        self._cache_dir = cache_dir
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache = DiskCache(str(self._cache_dir))

    def get_api_item(self, item_id: int) -> GW2Item | None:
        return self._cache.get(f"api:item:{item_id}")

    def set_api_item(self, item_id: int, data: GW2Item) -> None:
        self._cache.set(f"api:item:{item_id}", data, expire=None, tag="api")

    def get_api_recipe(self, recipe_id: int) -> GW2Recipe | None:
        return self._cache.get(f"api:recipe:{recipe_id}")

    def set_api_recipe(self, recipe_id: int, data: GW2Recipe) -> None:
        self._cache.set(f"api:recipe:{recipe_id}", data, expire=None, tag="api")

    def get_api_recipes_search(self, item_id: int) -> list[int] | None:
        return self._cache.get(f"api:recipes_search:{item_id}")

    def set_api_recipes_search(self, item_id: int, recipe_ids: list[int]) -> None:
        self._cache.set(f"api:recipes_search:{item_id}", recipe_ids, expire=None, tag="api")

    def get_wiki_page(self, page_name: str) -> str | None:
        return self._cache.get(f"wiki:{page_name}")

    def set_wiki_page(self, page_name: str, content: str) -> None:
        self._cache.set(f"wiki:{page_name}", content, expire=None, tag="wiki")

    def get_llm_extraction(
        self, item_id: int, item_name: str, content_hash: str, model: str
    ) -> dict | None:
        return self._cache.get(f"llm:{item_id}:{item_name}:{content_hash}:{model}")

    def set_llm_extraction(
        self, item_id: int, item_name: str, content_hash: str, model: str, data: dict
    ) -> None:
        self._cache.set(
            f"llm:{item_id}:{item_name}:{content_hash}:{model}",
            data,
            expire=7 * 86400,
            tag="llm",
        )

    def clear_cache(self, tags: list[str] | None = None) -> None:
        if tags:
            for tag in tags:
                self._cache.evict(tag)
        else:
            self._cache.clear()
