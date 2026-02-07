"""Tests for cache module."""

from pathlib import Path

import pytest

from gw2_data.cache import CacheClient


@pytest.fixture
def cache_client(tmp_path: Path) -> CacheClient:
    return CacheClient(tmp_path / "test_cache")


def test_cache_client_creates_directory(tmp_path: Path):
    test_cache_dir = tmp_path / "test_cache"

    CacheClient(test_cache_dir)

    assert test_cache_dir.exists()


def test_api_item_cache_roundtrip(cache_client: CacheClient):
    item_data = {
        "id": 123,
        "name": "Test Item",
        "type": "Weapon",
        "rarity": "Exotic",
        "level": 80,
    }

    cache_client.set_api_item(123, item_data)
    result = cache_client.get_api_item(123)

    assert result == item_data


def test_api_item_cache_miss(cache_client: CacheClient):
    result = cache_client.get_api_item(999999)

    assert result is None


def test_api_recipe_cache_roundtrip(cache_client: CacheClient):
    recipe_data = {
        "id": 456,
        "type": "Refinement",
        "output_item_id": 123,
        "output_item_count": 1,
        "min_rating": 400,
        "disciplines": ["Weaponsmith"],
        "ingredients": [{"item_id": 789, "count": 5}],
    }

    cache_client.set_api_recipe(456, recipe_data)
    result = cache_client.get_api_recipe(456)

    assert result == recipe_data


def test_api_recipes_search_cache_roundtrip(cache_client: CacheClient):
    recipe_ids = [1, 2, 3, 4, 5]

    cache_client.set_api_recipes_search(123, recipe_ids)
    result = cache_client.get_api_recipes_search(123)

    assert result == recipe_ids


def test_wiki_page_cache_roundtrip(cache_client: CacheClient):
    html = "<html><body>Test wiki content</body></html>"

    cache_client.set_wiki_page("Test_Item", html)
    result = cache_client.get_wiki_page("Test_Item")

    assert result == html


def test_llm_extraction_cache_roundtrip(cache_client: CacheClient):
    extraction_data = {
        "itemId": 123,
        "itemName": "Test Item",
        "wikiUrl": "https://wiki.example.com/Test_Item",
        "lastUpdated": "2025-01-15",
        "acquisitions": [],
    }

    cache_client.set_llm_extraction(123, "Test Item", "abc123", "haiku", "Exotic", extraction_data)
    result = cache_client.get_llm_extraction(123, "Test Item", "abc123", "haiku", "Exotic")

    assert result == extraction_data


def test_llm_extraction_cache_includes_item_name_in_key(cache_client: CacheClient):
    data1 = {"data": "first"}
    data2 = {"data": "second"}

    cache_client.set_llm_extraction(123, "Item A", "hash1", "haiku", "Exotic", data1)
    cache_client.set_llm_extraction(123, "Item B", "hash1", "haiku", "Exotic", data2)

    result1 = cache_client.get_llm_extraction(123, "Item A", "hash1", "haiku", "Exotic")
    result2 = cache_client.get_llm_extraction(123, "Item B", "hash1", "haiku", "Exotic")

    assert result1 == data1
    assert result2 == data2


def test_llm_extraction_cache_includes_model_in_key(cache_client: CacheClient):
    data_haiku = {"data": "haiku result"}
    data_sonnet = {"data": "sonnet result"}

    cache_client.set_llm_extraction(123, "Test Item", "abc123", "haiku", "Exotic", data_haiku)
    cache_client.set_llm_extraction(123, "Test Item", "abc123", "sonnet", "Exotic", data_sonnet)

    result_haiku = cache_client.get_llm_extraction(123, "Test Item", "abc123", "haiku", "Exotic")
    result_sonnet = cache_client.get_llm_extraction(123, "Test Item", "abc123", "sonnet", "Exotic")

    assert result_haiku == data_haiku
    assert result_sonnet == data_sonnet


def test_clear_cache_by_tag(cache_client: CacheClient):
    item_data = {
        "id": 1,
        "name": "API Item",
        "type": "Weapon",
        "rarity": "Fine",
        "level": 1,
    }
    cache_client.set_api_item(1, item_data)
    cache_client.set_wiki_page("Wiki Page", "content")

    cache_client.clear_cache(["api"])

    assert cache_client.get_api_item(1) is None
    assert cache_client.get_wiki_page("Wiki Page") == "content"


def test_clear_cache_all(cache_client: CacheClient):
    item_data = {
        "id": 1,
        "name": "API Item",
        "type": "Weapon",
        "rarity": "Fine",
        "level": 1,
    }
    cache_client.set_api_item(1, item_data)
    cache_client.set_wiki_page("Wiki Page", "content")

    cache_client.clear_cache()

    assert cache_client.get_api_item(1) is None
    assert cache_client.get_wiki_page("Wiki Page") is None


def test_llm_extraction_cache_includes_rarity_in_key(cache_client: CacheClient):
    legendary_data = {"acquisitions": [{"type": "mystic_forge"}]}
    ascended_data = {"acquisitions": [{"type": "vendor"}]}

    cache_client.set_llm_extraction(
        83162, "Ardent Glorious Armguards", "abc123", "haiku", "Legendary", legendary_data
    )
    cache_client.set_llm_extraction(
        67131, "Ardent Glorious Armguards", "abc123", "haiku", "Ascended", ascended_data
    )

    result_legendary = cache_client.get_llm_extraction(
        83162, "Ardent Glorious Armguards", "abc123", "haiku", "Legendary"
    )
    result_ascended = cache_client.get_llm_extraction(
        67131, "Ardent Glorious Armguards", "abc123", "haiku", "Ascended"
    )

    assert result_legendary == legendary_data
    assert result_ascended == ascended_data


def test_llm_extraction_cache_miss_on_different_rarity(cache_client: CacheClient):
    data = {"acquisitions": []}

    cache_client.set_llm_extraction(123, "Test Item", "abc123", "haiku", "Exotic", data)
    result = cache_client.get_llm_extraction(123, "Test Item", "abc123", "haiku", "Rare")

    assert result is None


def test_llm_extraction_cache_hit_requires_exact_rarity_match(cache_client: CacheClient):
    legendary_data = {"acquisitions": [{"type": "mystic_forge"}]}

    cache_client.set_llm_extraction(
        83162, "Ardent Glorious Armguards", "abc123", "haiku", "Legendary", legendary_data
    )

    result = cache_client.get_llm_extraction(
        83162, "Ardent Glorious Armguards", "abc123", "haiku", "Legendary"
    )
    assert result == legendary_data

    miss_result = cache_client.get_llm_extraction(
        83162, "Ardent Glorious Armguards", "abc123", "haiku", "Ascended"
    )
    assert miss_result is None
