"""Tests for bulk API functions and build_index script."""

from collections import defaultdict
from pathlib import Path

import pytest
import yaml
from httpx import HTTPStatusError, Request, RequestError, Response

from gw2_data import api
from gw2_data.cache import CacheClient
from gw2_data.exceptions import APIError
from gw2_data.types import BulkResult


@pytest.fixture
def cache_client(tmp_path: Path) -> CacheClient:
    return CacheClient(tmp_path / "test_cache")


ITEM_A = {"id": 1, "name": "Sword", "type": "Weapon", "rarity": "Exotic", "level": 80}
ITEM_B = {"id": 2, "name": "Shield", "type": "Weapon", "rarity": "Rare", "level": 80}
ITEM_C = {"id": 3, "name": "Sword", "type": "Weapon", "rarity": "Fine", "level": 20}


# --- get_all_item_ids ---


def test_get_all_item_ids_success(mocker):
    mock_get = mocker.patch("httpx.get")
    mock_get.return_value.json.return_value = [1, 2, 3]
    mock_get.return_value.raise_for_status = lambda: None

    result = api.get_all_item_ids()

    assert result == [1, 2, 3]
    mock_get.assert_called_once()


def test_get_all_item_ids_http_error(mocker):
    mock_get = mocker.patch("httpx.get")
    mock_response = Response(500, request=Request("GET", "http://test.com"))
    mock_get.return_value.raise_for_status.side_effect = HTTPStatusError(
        "Server error", request=mock_response.request, response=mock_response
    )

    with pytest.raises(APIError, match="Failed to fetch item IDs: HTTP 500"):
        api.get_all_item_ids()


def test_get_all_item_ids_network_error(mocker):
    mock_get = mocker.patch("httpx.get")
    mock_get.side_effect = RequestError("Connection failed")

    with pytest.raises(APIError, match="Network error fetching item IDs"):
        api.get_all_item_ids()


# --- get_items_bulk ---


def test_get_items_bulk_success(mocker, cache_client: CacheClient):
    mock_get = mocker.patch("httpx.get")
    mock_get.return_value.json.return_value = [ITEM_A, ITEM_B]
    mock_get.return_value.raise_for_status = lambda: None

    result = api.get_items_bulk([1, 2], cache_client)

    assert result.items == [ITEM_A, ITEM_B]
    assert result.from_cache is False
    mock_get.assert_called_once()
    assert cache_client.get_api_item(1) == ITEM_A
    assert cache_client.get_api_item(2) == ITEM_B


def test_get_items_bulk_all_cached(mocker, cache_client: CacheClient):
    cache_client.set_api_item(1, ITEM_A)
    cache_client.set_api_item(2, ITEM_B)
    mock_get = mocker.patch("httpx.get")

    result = api.get_items_bulk([1, 2], cache_client)

    assert result.items == [ITEM_A, ITEM_B]
    assert result.from_cache is True
    mock_get.assert_not_called()


def test_get_items_bulk_partial_cache_miss(mocker, cache_client: CacheClient):
    cache_client.set_api_item(1, ITEM_A)
    mock_get = mocker.patch("httpx.get")
    mock_get.return_value.json.return_value = [ITEM_A, ITEM_B]
    mock_get.return_value.raise_for_status = lambda: None

    result = api.get_items_bulk([1, 2], cache_client)

    assert result.items == [ITEM_A, ITEM_B]
    assert result.from_cache is False
    mock_get.assert_called_once()


def test_get_items_bulk_force_bypasses_cache(mocker, cache_client: CacheClient):
    cache_client.set_api_item(1, ITEM_A)
    cache_client.set_api_item(2, ITEM_B)
    mock_get = mocker.patch("httpx.get")
    mock_get.return_value.json.return_value = [ITEM_A, ITEM_B]
    mock_get.return_value.raise_for_status = lambda: None

    result = api.get_items_bulk([1, 2], cache_client, force=True)

    assert result.items == [ITEM_A, ITEM_B]
    assert result.from_cache is False
    mock_get.assert_called_once()


def test_get_items_bulk_empty_list(cache_client: CacheClient):
    result = api.get_items_bulk([], cache_client)
    assert result.items == []
    assert result.from_cache is True


def test_get_items_bulk_over_200_raises(cache_client: CacheClient):
    with pytest.raises(APIError, match="Bulk fetch limited to 200"):
        api.get_items_bulk(list(range(201)), cache_client)


def test_get_items_bulk_http_error(mocker, cache_client: CacheClient):
    mock_get = mocker.patch("httpx.get")
    mock_response = Response(503, request=Request("GET", "http://test.com"))
    mock_get.return_value.raise_for_status.side_effect = HTTPStatusError(
        "Unavailable", request=mock_response.request, response=mock_response
    )

    with pytest.raises(APIError, match="Failed to fetch item batch: HTTP 503"):
        api.get_items_bulk([1, 2], cache_client)


# --- load_item_name_index ---


def test_load_item_name_index_success(monkeypatch, tmp_path: Path):
    index_data = {"Sword": [1, 3], "Shield": [2]}
    index_dir = tmp_path / "data" / "index"
    index_dir.mkdir(parents=True)
    index_file = index_dir / "item_names.yaml"
    index_file.write_text(yaml.dump(index_data))

    config_dir = tmp_path / "overrides"
    config_dir.mkdir()

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(api, "_CONFIG_DIR", config_dir)

    result = api.load_item_name_index()
    assert result == {"Sword": [1, 3], "Shield": [2]}


def test_load_item_name_index_missing(monkeypatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)

    with pytest.raises(APIError, match="Item name index not found"):
        api.load_item_name_index()


# --- build_index integration ---


def test_build_index_writes_sorted_yaml(mocker, tmp_path: Path):
    from scripts.build_index import build_item_index

    cache = CacheClient(tmp_path / "cache")
    mocker.patch.object(api, "get_all_item_ids", return_value=[1, 2, 3])
    mocker.patch.object(
        api,
        "get_items_bulk",
        return_value=BulkResult(items=[ITEM_A, ITEM_B, ITEM_C], from_cache=False),
    )

    index_path = tmp_path / "index" / "item_names.yaml"
    mocker.patch("scripts.build_index.INDEX_DIR", tmp_path / "index")
    mocker.patch("scripts.build_index.ITEM_NAMES_PATH", index_path)
    mocker.patch("scripts.build_index.BATCH_DELAY", 0)

    build_item_index(cache)

    assert index_path.exists()
    index = yaml.safe_load(index_path.read_text())
    assert list(index.keys()) == ["Shield", "Sword"]
    assert index["Sword"] == [1, 3]
    assert index["Shield"] == [2]


def test_build_index_retries_failed_batches(mocker, tmp_path: Path):
    from scripts.build_index import build_item_index

    cache = CacheClient(tmp_path / "cache")
    mocker.patch.object(api, "get_all_item_ids", return_value=[1, 2])

    call_count = 0

    def mock_bulk(ids, c, *, force=False):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise APIError("Temporary failure")
        return BulkResult(items=[ITEM_A, ITEM_B], from_cache=False)

    mocker.patch.object(api, "get_items_bulk", side_effect=mock_bulk)

    index_path = tmp_path / "index" / "item_names.yaml"
    mocker.patch("scripts.build_index.INDEX_DIR", tmp_path / "index")
    mocker.patch("scripts.build_index.ITEM_NAMES_PATH", index_path)
    mocker.patch("scripts.build_index.BATCH_DELAY", 0)

    build_item_index(cache)

    assert index_path.exists()
    index = yaml.safe_load(index_path.read_text())
    assert "Sword" in index
    assert "Shield" in index


def test_build_index_uses_flow_style_lists(mocker, tmp_path: Path):
    from scripts.build_index import build_item_index

    cache = CacheClient(tmp_path / "cache")
    mocker.patch.object(api, "get_all_item_ids", return_value=[1, 2, 3])
    mocker.patch.object(
        api,
        "get_items_bulk",
        return_value=BulkResult(items=[ITEM_A, ITEM_B, ITEM_C], from_cache=False),
    )

    index_path = tmp_path / "index" / "item_names.yaml"
    mocker.patch("scripts.build_index.INDEX_DIR", tmp_path / "index")
    mocker.patch("scripts.build_index.ITEM_NAMES_PATH", index_path)
    mocker.patch("scripts.build_index.BATCH_DELAY", 0)

    build_item_index(cache)

    raw = index_path.read_text()
    assert "[1, 3]" in raw
    assert "[2]" in raw


# --- name cleaning ---


def test_index_item_skips_empty_name():
    from scripts.build_index import _index_item

    name_index: dict[str, list[int]] = {}
    skipped: list[int] = []
    cleaned: list[tuple[int, str]] = []

    item = {"id": 99, "name": "", "type": "Weapon", "rarity": "Basic", "level": 0}
    _index_item(item, name_index, skipped, cleaned)

    assert skipped == [99]
    assert name_index == {}
    assert cleaned == []


def test_index_item_skips_whitespace_only_name():
    from scripts.build_index import _index_item

    name_index: dict[str, list[int]] = {}
    skipped: list[int] = []
    cleaned: list[tuple[int, str]] = []

    _index_item(
        {"id": 50, "name": "   ", "type": "Weapon", "rarity": "Basic", "level": 0},
        name_index,
        skipped,
        cleaned,
    )

    assert skipped == [50]
    assert name_index == {}


def test_index_item_strips_newlines():
    from scripts.build_index import _index_item

    name_index: dict[str, list[int]] = defaultdict(list)
    skipped: list[int] = []
    cleaned: list[tuple[int, str]] = []

    _index_item(
        {"id": 7, "name": "Cool\nSword", "type": "Weapon", "rarity": "Exotic", "level": 80},
        name_index,
        skipped,
        cleaned,
    )

    assert "Cool Sword" in name_index
    assert name_index["Cool Sword"] == [7]
    assert len(cleaned) == 1
    assert cleaned[0][0] == 7


def test_index_item_normal_name():
    from scripts.build_index import _index_item

    name_index: dict[str, list[int]] = defaultdict(list)
    skipped: list[int] = []
    cleaned: list[tuple[int, str]] = []

    _index_item(ITEM_A, name_index, skipped, cleaned)

    assert name_index["Sword"] == [1]
    assert skipped == []
    assert cleaned == []


def test_index_item_strips_leading_whitespace():
    from scripts.build_index import _index_item

    name_index: dict[str, list[int]] = defaultdict(list)
    skipped: list[int] = []
    cleaned: list[tuple[int, str]] = []

    _index_item(
        {"id": 42, "name": " Mastery Point", "type": "Trophy", "rarity": "Basic", "level": 0},
        name_index,
        skipped,
        cleaned,
    )

    assert "Mastery Point" in name_index
    assert name_index["Mastery Point"] == [42]
    assert skipped == []
    assert cleaned == []


def test_index_item_cleans_multiline_name():
    from scripts.build_index import _index_item

    name_index: dict[str, list[int]] = defaultdict(list)
    skipped: list[int] = []
    cleaned: list[tuple[int, str]] = []

    _index_item(
        {
            "id": 99,
            "name": "Abelin Favre\n543 Bloom X011\nCelestial",
            "type": "Armor",
            "rarity": "Exotic",
            "level": 80,
        },
        name_index,
        skipped,
        cleaned,
    )

    assert "Abelin Favre 543 Bloom X011 Celestial" in name_index
    assert name_index["Abelin Favre 543 Bloom X011 Celestial"] == [99]
    assert len(cleaned) == 1
    assert cleaned[0][0] == 99


# --- populate.py --item-name resolution ---


def test_item_name_resolution_single_match(mocker, monkeypatch, tmp_path: Path, capsys):
    index_data = {"Gift of Metal": [19676]}
    currency_data = {"Coin": 1}
    index_dir = tmp_path / "data" / "index"
    index_dir.mkdir(parents=True)
    index_file = index_dir / "item_names.yaml"
    index_file.write_text(yaml.dump(index_data))
    currency_file = index_dir / "currency_names.yaml"
    currency_file.write_text(yaml.dump(currency_data))

    monkeypatch.chdir(tmp_path)

    mock_item = {
        "id": 19676,
        "name": "Gift of Metal",
        "type": "Trophy",
        "rarity": "Legendary",
        "level": 0,
    }
    mocker.patch.object(api, "get_item", return_value=mock_item)
    mocker.patch("scripts.populate.wiki.get_page_html", return_value="<html>test</html>")
    mocker.patch(
        "scripts.populate.llm.extract_entries",
        return_value=mocker.Mock(
            entries=[],
            overall_confidence=1.0,
            entry_confidences=[],
            notes="",
        ),
    )
    mocker.patch.object(api, "load_gathering_node_index", return_value=set())

    from scripts import populate

    cache = CacheClient(tmp_path / "cache")

    populate.populate_item(19676, cache, dry_run=True)

    captured = capsys.readouterr()
    assert "Gift of Metal" in captured.out


def test_item_name_resolution_no_match(monkeypatch, tmp_path: Path):
    index_data = {"Gift of Metal": [19676]}
    index_dir = tmp_path / "data" / "index"
    index_dir.mkdir(parents=True)
    index_file = index_dir / "item_names.yaml"
    index_file.write_text(yaml.dump(index_data))

    monkeypatch.chdir(tmp_path)

    index = api.load_item_name_index()
    matches = index.get("Nonexistent Item")

    assert matches is None


def test_item_name_resolution_multiple_matches(monkeypatch, tmp_path: Path):
    index_data = {"Sword": [1, 3]}
    index_dir = tmp_path / "data" / "index"
    index_dir.mkdir(parents=True)
    index_file = index_dir / "item_names.yaml"
    index_file.write_text(yaml.dump(index_data))

    monkeypatch.chdir(tmp_path)

    index = api.load_item_name_index()
    matches = index.get("Sword")

    assert matches == [1, 3]
    assert len(matches) > 1


def test_clean_name_normalizes_whitespace():
    assert api.clean_name("  Item Name  ") == "Item Name"
    assert api.clean_name("Item\nName") == "Item Name"
    assert api.clean_name("Item   Name") == "Item Name"
    assert api.clean_name("  Item  \n  Name  \r\n  Test  ") == "Item Name Test"


# --- build_currency_index ---


def test_build_currency_index_success(mocker, tmp_path: Path):
    from scripts.build_index import build_currency_index

    mock_currencies = [
        {"id": 1, "name": "Coin"},
        {"id": 2, "name": "Karma"},
        {"id": 3, "name": "Laurel"},
    ]

    mock_get = mocker.patch("httpx.get")
    mock_response = mocker.Mock()
    mock_response.json.return_value = mock_currencies
    mock_response.raise_for_status = mocker.Mock()
    mock_get.return_value = mock_response

    index_path = tmp_path / "index" / "currency_names.yaml"
    mocker.patch("scripts.build_index.INDEX_DIR", tmp_path / "index")
    mocker.patch("scripts.build_index.CURRENCY_NAMES_PATH", index_path)

    build_currency_index()

    assert index_path.exists()
    index = yaml.safe_load(index_path.read_text())
    assert index == {"Coin": 1, "Karma": 2, "Laurel": 3}


def test_build_currency_index_skips_empty_names(mocker, tmp_path: Path):
    from scripts.build_index import build_currency_index

    mock_currencies = [
        {"id": 1, "name": "Coin"},
        {"id": 74, "name": ""},
        {"id": 2, "name": "Karma"},
    ]

    mock_get = mocker.patch("httpx.get")
    mock_response = mocker.Mock()
    mock_response.json.return_value = mock_currencies
    mock_response.raise_for_status = mocker.Mock()
    mock_get.return_value = mock_response

    index_path = tmp_path / "index" / "currency_names.yaml"
    mocker.patch("scripts.build_index.INDEX_DIR", tmp_path / "index")
    mocker.patch("scripts.build_index.CURRENCY_NAMES_PATH", index_path)

    build_currency_index()

    assert index_path.exists()
    index = yaml.safe_load(index_path.read_text())
    assert index == {"Coin": 1, "Karma": 2}
    assert 74 not in index.values()


def test_build_currency_index_http_error(mocker):

    from gw2_data.exceptions import APIError
    from scripts.build_index import build_currency_index

    mock_get = mocker.patch("httpx.get")
    mock_response = Response(500, request=Request("GET", "http://test.com"))
    mock_get.return_value.raise_for_status.side_effect = HTTPStatusError(
        "Server error", request=mock_response.request, response=mock_response
    )

    with pytest.raises(APIError, match="Failed to fetch currencies"):
        build_currency_index()


def test_build_currency_index_sorts_alphabetically(mocker, tmp_path: Path):
    from scripts.build_index import build_currency_index

    mock_currencies = [
        {"id": 3, "name": "Zebra Coin"},
        {"id": 1, "name": "Apple Coin"},
        {"id": 2, "name": "Banana Coin"},
    ]

    mock_get = mocker.patch("httpx.get")
    mock_response = mocker.Mock()
    mock_response.json.return_value = mock_currencies
    mock_response.raise_for_status = mocker.Mock()
    mock_get.return_value = mock_response

    index_path = tmp_path / "index" / "currency_names.yaml"
    mocker.patch("scripts.build_index.INDEX_DIR", tmp_path / "index")
    mocker.patch("scripts.build_index.CURRENCY_NAMES_PATH", index_path)

    build_currency_index()

    index = yaml.safe_load(index_path.read_text())
    keys = list(index.keys())
    assert keys == ["Apple Coin", "Banana Coin", "Zebra Coin"]


# --- API resolution functions ---


def test_resolve_item_name_to_id_success():
    index = {"Sword": [123]}
    result = api.resolve_item_name_to_id("Sword", index)
    assert result == 123


def test_resolve_item_name_to_id_cleans_name():
    index = {"Sword": [123]}
    result = api.resolve_item_name_to_id("  Sword  ", index)
    assert result == 123


def test_resolve_item_name_to_id_not_found():
    index = {"Sword": [123]}
    with pytest.raises(APIError, match="Item name 'Shield' not found"):
        api.resolve_item_name_to_id("Shield", index)


def test_resolve_item_name_to_id_multiple_matches():
    index = {"Sword": [123, 456]}
    with pytest.raises(APIError, match="matches multiple IDs"):
        api.resolve_item_name_to_id("Sword", index)


def test_resolve_currency_name_to_id_success():
    index = {"Coin": 1}
    result = api.resolve_currency_name_to_id("Coin", index)
    assert result == 1


def test_resolve_currency_name_to_id_cleans_name():
    index = {"Coin": 1}
    result = api.resolve_currency_name_to_id("  Coin  ", index)
    assert result == 1


def test_resolve_currency_name_to_id_not_found():
    index = {"Coin": 1}
    with pytest.raises(APIError, match="Currency name 'Karma' not found"):
        api.resolve_currency_name_to_id("Karma", index)
