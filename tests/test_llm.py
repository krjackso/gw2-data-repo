"""Tests for LLM extraction module."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from gw2_data import llm
from gw2_data.cache import CacheClient


@pytest.fixture
def cache_client(tmp_path: Path) -> CacheClient:
    return CacheClient(tmp_path / "test_cache")


def test_extract_acquisitions_returns_valid_structure(cache_client: CacheClient):
    item_id = 123
    item_name = "Test Item"
    wiki_html = "<html><body>Test acquisition info</body></html>"
    api_data = {
        "id": 123,
        "name": "Test Item",
        "type": "Weapon",
        "rarity": "Exotic",
        "level": 80,
    }

    result = llm.extract_acquisitions(item_id, item_name, wiki_html, api_data, cache=cache_client)

    assert result["itemId"] == item_id
    assert result["itemName"] == item_name
    assert result["wikiUrl"] == "https://wiki.guildwars2.com/wiki/Test_Item"
    assert "lastUpdated" in result
    assert "acquisitions" in result
    assert isinstance(result["acquisitions"], list)


def test_extract_acquisitions_uses_current_date(cache_client: CacheClient):
    item_id = 123
    item_name = "Test Item"
    wiki_html = "<html><body>Test</body></html>"
    api_data = {
        "id": 123,
        "name": "Test Item",
        "type": "Weapon",
        "rarity": "Exotic",
        "level": 80,
    }

    result = llm.extract_acquisitions(item_id, item_name, wiki_html, api_data, cache=cache_client)

    expected_date = datetime.now(UTC).date().isoformat()
    assert result["lastUpdated"] == expected_date


def test_extract_acquisitions_caches_result(cache_client: CacheClient):
    item_id = 123
    item_name = "Test Item"
    wiki_html = "<html><body>Test</body></html>"
    api_data = {
        "id": 123,
        "name": "Test Item",
        "type": "Weapon",
        "rarity": "Exotic",
        "level": 80,
    }

    result1 = llm.extract_acquisitions(item_id, item_name, wiki_html, api_data, cache=cache_client)
    result2 = llm.extract_acquisitions(item_id, item_name, wiki_html, api_data, cache=cache_client)

    assert result1 == result2


def test_extract_acquisitions_different_content_different_cache(mocker):
    item_id = 123
    item_name = "Test Item"
    wiki_html1 = "<html><body>Version 1</body></html>"
    wiki_html2 = "<html><body>Version 2</body></html>"
    api_data = {
        "id": 123,
        "name": "Test Item",
        "type": "Weapon",
        "rarity": "Exotic",
        "level": 80,
    }

    mock_cache = mocker.Mock()
    mock_cache.get_llm_extraction.return_value = None

    llm.extract_acquisitions(item_id, item_name, wiki_html1, api_data, cache=mock_cache)
    llm.extract_acquisitions(item_id, item_name, wiki_html2, api_data, cache=mock_cache)

    assert mock_cache.set_llm_extraction.call_count == 2
    call1_hash = mock_cache.set_llm_extraction.call_args_list[0][0][2]
    call2_hash = mock_cache.set_llm_extraction.call_args_list[1][0][2]
    assert call1_hash != call2_hash


def test_extract_acquisitions_wiki_url_handles_spaces(cache_client: CacheClient):
    item_id = 123
    item_name = "Test Item With Spaces"
    wiki_html = "<html><body>Test</body></html>"
    api_data = {
        "id": 123,
        "name": "Test Item With Spaces",
        "type": "Weapon",
        "rarity": "Exotic",
        "level": 80,
    }

    result = llm.extract_acquisitions(item_id, item_name, wiki_html, api_data, cache=cache_client)

    assert result["wikiUrl"] == "https://wiki.guildwars2.com/wiki/Test_Item_With_Spaces"
