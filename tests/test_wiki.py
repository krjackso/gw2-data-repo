"""Tests for wiki module."""

from pathlib import Path

import pytest
from httpx import HTTPStatusError, Request, RequestError, Response

from gw2_data import wiki
from gw2_data.cache import CacheClient
from gw2_data.exceptions import WikiError


@pytest.fixture
def cache_client(tmp_path: Path) -> CacheClient:
    return CacheClient(tmp_path / "test_cache")


def test_get_page_html_success(mocker, cache_client: CacheClient):
    mock_html = "<html><body>Test content</body></html>"
    mock_response_data = {"parse": {"text": {"*": mock_html}}}
    mock_get = mocker.patch("httpx.get")
    mock_get.return_value.json.return_value = mock_response_data
    mock_get.return_value.raise_for_status = lambda: None

    result = wiki.get_page_html("Test_Page", cache=cache_client)

    assert result == mock_html


def test_get_page_html_caches_result(mocker, cache_client: CacheClient):
    mock_html = "<html><body>Test content</body></html>"
    mock_response_data = {"parse": {"text": {"*": mock_html}}}
    mock_get = mocker.patch("httpx.get")
    mock_get.return_value.json.return_value = mock_response_data
    mock_get.return_value.raise_for_status = lambda: None

    result1 = wiki.get_page_html("Test_Page", cache=cache_client)
    result2 = wiki.get_page_html("Test_Page", cache=cache_client)

    assert result1 == result2
    assert mock_get.call_count == 1


def test_get_page_html_empty_name(cache_client: CacheClient):
    with pytest.raises(WikiError, match="Page name cannot be empty"):
        wiki.get_page_html("", cache=cache_client)

    with pytest.raises(WikiError, match="Page name cannot be empty"):
        wiki.get_page_html("   ", cache=cache_client)


def test_get_page_html_page_not_found(mocker, cache_client: CacheClient):
    mock_response_data = {"error": {"info": "The page does not exist"}}
    mock_get = mocker.patch("httpx.get")
    mock_get.return_value.json.return_value = mock_response_data
    mock_get.return_value.raise_for_status = lambda: None

    with pytest.raises(WikiError, match="not found"):
        wiki.get_page_html("Nonexistent_Page", cache=cache_client)


def test_get_page_html_http_error(mocker, cache_client: CacheClient):
    mock_get = mocker.patch("httpx.get")
    mock_response = Response(500, request=Request("GET", "http://test.com"))
    mock_get.return_value.raise_for_status.side_effect = HTTPStatusError(
        "Server error", request=mock_response.request, response=mock_response
    )

    with pytest.raises(WikiError, match="Failed to fetch wiki page.*HTTP 500"):
        wiki.get_page_html("Test_Page", cache=cache_client)


def test_get_page_html_network_error(mocker, cache_client: CacheClient):
    mock_get = mocker.patch("httpx.get")
    mock_get.side_effect = RequestError("Connection timeout")

    with pytest.raises(WikiError, match="Network error fetching wiki page"):
        wiki.get_page_html("Test_Page", cache=cache_client)


def test_get_page_html_invalid_json(mocker, cache_client: CacheClient):
    mock_get = mocker.patch("httpx.get")
    mock_get.return_value.json.side_effect = ValueError("Invalid JSON")
    mock_get.return_value.raise_for_status = lambda: None

    with pytest.raises(WikiError, match="Invalid JSON response"):
        wiki.get_page_html("Test_Page", cache=cache_client)


def test_get_page_html_unexpected_format(mocker, cache_client: CacheClient):
    mock_response_data = {"unexpected": "format"}
    mock_get = mocker.patch("httpx.get")
    mock_get.return_value.json.return_value = mock_response_data
    mock_get.return_value.raise_for_status = lambda: None

    with pytest.raises(WikiError, match="Unexpected wiki API response format"):
        wiki.get_page_html("Test_Page", cache=cache_client)
