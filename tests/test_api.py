"""Tests for API module."""

from pathlib import Path

import pytest
from httpx import HTTPStatusError, Request, RequestError, Response

from gw2_data import api
from gw2_data.cache import CacheClient
from gw2_data.exceptions import APIError


@pytest.fixture
def cache_client(tmp_path: Path) -> CacheClient:
    return CacheClient(tmp_path / "test_cache")


def test_get_item_success(mocker, cache_client: CacheClient):
    mock_response = {
        "id": 123,
        "name": "Test Item",
        "type": "Weapon",
        "rarity": "Exotic",
        "level": 80,
    }
    mock_get = mocker.patch("httpx.get")
    mock_get.return_value.json.return_value = mock_response
    mock_get.return_value.raise_for_status = lambda: None

    result = api.get_item(123, cache=cache_client)

    assert result == mock_response
    mock_get.assert_called_once()


def test_get_item_caches_result(mocker, cache_client: CacheClient):
    mock_response = {
        "id": 123,
        "name": "Test Item",
        "type": "Weapon",
        "rarity": "Exotic",
        "level": 80,
    }
    mock_get = mocker.patch("httpx.get")
    mock_get.return_value.json.return_value = mock_response
    mock_get.return_value.raise_for_status = lambda: None

    result1 = api.get_item(123, cache=cache_client)
    result2 = api.get_item(123, cache=cache_client)

    assert result1 == result2
    assert mock_get.call_count == 1


def test_get_item_invalid_id(cache_client: CacheClient):
    with pytest.raises(APIError, match="Invalid item ID"):
        api.get_item(0, cache=cache_client)

    with pytest.raises(APIError, match="Invalid item ID"):
        api.get_item(-1, cache=cache_client)


def test_get_item_http_error(mocker, cache_client: CacheClient):
    mock_get = mocker.patch("httpx.get")
    mock_response = Response(404, request=Request("GET", "http://test.com"))
    mock_get.return_value.raise_for_status.side_effect = HTTPStatusError(
        "Not found", request=mock_response.request, response=mock_response
    )

    with pytest.raises(APIError, match="Failed to fetch item 123: HTTP 404"):
        api.get_item(123, cache=cache_client)


def test_get_item_network_error(mocker, cache_client: CacheClient):
    mock_get = mocker.patch("httpx.get")
    mock_get.side_effect = RequestError("Connection failed")

    with pytest.raises(APIError, match="Network error fetching item 123"):
        api.get_item(123, cache=cache_client)


def test_get_recipe_success(mocker, cache_client: CacheClient):
    mock_response = {
        "id": 456,
        "type": "Refinement",
        "output_item_id": 123,
        "output_item_count": 1,
        "min_rating": 400,
        "disciplines": ["Weaponsmith"],
        "ingredients": [{"item_id": 789, "count": 5}],
    }
    mock_get = mocker.patch("httpx.get")
    mock_get.return_value.json.return_value = mock_response
    mock_get.return_value.raise_for_status = lambda: None

    result = api.get_recipe(456, cache=cache_client)

    assert result == mock_response


def test_get_recipe_invalid_id(cache_client: CacheClient):
    with pytest.raises(APIError, match="Invalid recipe ID"):
        api.get_recipe(0, cache=cache_client)


def test_search_recipes_by_output_success(mocker, cache_client: CacheClient):
    mock_response = [1, 2, 3, 4, 5]
    mock_get = mocker.patch("httpx.get")
    mock_get.return_value.json.return_value = mock_response
    mock_get.return_value.raise_for_status = lambda: None

    result = api.search_recipes_by_output(123, cache=cache_client)

    assert result == mock_response


def test_search_recipes_by_output_invalid_id(cache_client: CacheClient):
    with pytest.raises(APIError, match="Invalid item ID"):
        api.search_recipes_by_output(-5, cache=cache_client)


def test_search_recipes_by_output_caches_result(mocker, cache_client: CacheClient):
    mock_response = [1, 2, 3]
    mock_get = mocker.patch("httpx.get")
    mock_get.return_value.json.return_value = mock_response
    mock_get.return_value.raise_for_status = lambda: None

    result1 = api.search_recipes_by_output(123, cache=cache_client)
    result2 = api.search_recipes_by_output(123, cache=cache_client)

    assert result1 == result2
    assert mock_get.call_count == 1
