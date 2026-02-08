"""Tests for wiki module."""

from pathlib import Path

import pytest
from httpx import HTTPStatusError, Request, RequestError, Response

from gw2_data import wiki
from gw2_data.cache import CacheClient
from gw2_data.exceptions import WikiError

# --- extract_acquisition_sections tests ---


def _make_large_html(sections: list[str], bulk_size: int = 400_000) -> str:
    excluded_bulk = '<h2><span id="Gallery">Gallery</span></h2>' + "<p>" + "g" * bulk_size + "</p>"
    return "\n".join(sections) + excluded_bulk


class TestExtractAcquisitionSections:
    def test_small_html_returned_unchanged(self):
        html = "<p>Small page</p>"
        assert wiki.extract_acquisition_sections(html) == html

    def test_excluded_h3_does_not_swallow_sibling_h3(self):
        html = _make_large_html(
            [
                '<h2><span id="Acquisition">Acquisition</span></h2>',
                "<p>Intro text</p>",
                '<h3><span id="Dropped_by">Dropped by</span></h3>',
                "<p>Monster drop table with lots of data</p>",
                '<h3><span id="Recipe">Recipe</span></h3>',
                "<p>Mystic Forge promotion recipe</p>",
                '<h2><span id="Used_in">Used in</span></h2>',
                "<p>Crafting recipes</p>",
            ]
        )
        result = wiki.extract_acquisition_sections(html)
        assert "Recipe" in result
        assert "Mystic Forge promotion recipe" in result
        assert "Monster drop table" not in result

    def test_excluded_h3_contained_in_does_not_swallow_siblings(self):
        html = _make_large_html(
            [
                '<h2><span id="Acquisition">Acquisition</span></h2>',
                '<h3><span id="Contained_in">Contained in</span></h3>',
                "<p>Container list</p>",
                '<h3><span id="Map_Bonus_Reward">Map Bonus Reward</span></h3>',
                "<p>Map reward info</p>",
                '<h3><span id="Reward_tracks">Reward tracks</span></h3>',
                "<p>Reward track info</p>",
                '<h3><span id="Recipe">Recipe</span></h3>',
                "<p>Recipe data</p>",
                '<h2><span id="Used_in">Used in</span></h2>',
            ]
        )
        result = wiki.extract_acquisition_sections(html)
        assert "Container list" not in result
        assert "Map reward info" in result
        assert "Reward track info" in result
        assert "Recipe data" in result

    def test_h2_used_in_still_fully_excluded(self):
        html = _make_large_html(
            [
                '<h2><span id="Acquisition">Acquisition</span></h2>',
                "<p>Acquisition info</p>",
                '<h2><span id="Used_in">Used in</span></h2>',
                '<h3><span id="Mystic_Forge">Mystic Forge</span></h3>',
                "<p>Used in recipes</p>",
                '<h3><span id="Armorsmith">Armorsmith</span></h3>',
                "<p>Armorsmith recipes</p>",
            ]
        )
        result = wiki.extract_acquisition_sections(html)
        assert "Acquisition info" in result
        assert "Used in recipes" not in result
        assert "Armorsmith recipes" not in result


class TestGetHtmlLimitForModel:
    def test_haiku_limit(self):
        assert wiki.get_html_limit_for_model("haiku") == 300_000

    def test_sonnet_limit(self):
        assert wiki.get_html_limit_for_model("sonnet") == 600_000

    def test_opus_limit(self):
        assert wiki.get_html_limit_for_model("opus") == 600_000

    def test_full_model_name_haiku(self):
        assert wiki.get_html_limit_for_model("claude-haiku-4-5-20250929") == 300_000

    def test_full_model_name_sonnet(self):
        assert wiki.get_html_limit_for_model("claude-sonnet-4-5-20250929") == 600_000

    def test_full_model_name_opus(self):
        assert wiki.get_html_limit_for_model("claude-opus-4-6") == 600_000

    def test_unknown_model_uses_default(self):
        assert wiki.get_html_limit_for_model("unknown-model") == 300_000


class TestExtractAcquisitionSectionsMaxLength:
    def test_larger_limit_preserves_more_content(self):
        large_content = "<p>" + "x" * 500_000 + "</p>"
        result_default = wiki.extract_acquisition_sections(large_content)
        result_large = wiki.extract_acquisition_sections(large_content, max_length=600_000)
        assert len(result_default) == 300_000
        assert len(result_large) == len(large_content)

    def test_truncation_respects_custom_limit(self):
        large_content = "<p>" + "x" * 500_000 + "</p>"
        result = wiki.extract_acquisition_sections(large_content, max_length=300_000)
        assert len(result) == 300_000

    def test_default_limit_unchanged(self):
        large_content = "<p>" + "x" * 400_000 + "</p>"
        result = wiki.extract_acquisition_sections(large_content)
        assert len(result) == 300_000


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


# --- Disambiguation detection tests ---

_DISAMBIG_IMG = (
    '<img alt="Disambig icon.png"'
    ' src="/images/thumb/6/67/Disambig_icon.png/19px-Disambig_icon.png" />'
)
_DISAMBIG_HTML = (
    '<div class="noexcerpt"><div style="margin-left:1.6em;">'
    f"{_DISAMBIG_IMG}"
    " <i>This article is about the skill. "
    "For the item, see "
    '<a href="/wiki/Mirror_(item)" title="Mirror (item)">'
    "Mirror (item)</a>."
    "</i></div></div>"
    "<p>Mirror is a mesmer skill...</p>"
)


def test_find_item_disambiguation_detects_redirect():
    result = wiki._find_item_disambiguation(_DISAMBIG_HTML, "Mirror")
    assert result == "Mirror (item)"


def test_find_item_disambiguation_no_disambig_marker():
    html = "<p>Normal page content about Mirror</p>"
    result = wiki._find_item_disambiguation(html, "Mirror")
    assert result is None


def test_find_item_disambiguation_no_item_link():
    html = (
        f"{_DISAMBIG_IMG}"
        " <i>For the other thing, see "
        '<a href="/wiki/Mirror_(skill)">Mirror (skill)</a>.</i>'
    )
    result = wiki._find_item_disambiguation(html, "Mirror")
    assert result is None


def test_find_item_disambiguation_multi_word_name():
    html = (
        f"{_DISAMBIG_IMG}"
        " <i>For the item, see "
        '<a href="/wiki/Pile_of_Sand_(item)">'
        "Pile of Sand (item)</a>.</i>"
    )
    result = wiki._find_item_disambiguation(html, "Pile of Sand")
    assert result == "Pile of Sand (item)"


def test_get_page_html_follows_disambiguation(mocker, cache_client: CacheClient):
    item_html = "<p>Mirror is a crafting material...</p>"
    call_count = 0

    def mock_get_side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        mock_resp = mocker.MagicMock()
        mock_resp.raise_for_status = lambda: None
        if call_count == 1:
            mock_resp.json.return_value = {"parse": {"text": {"*": _DISAMBIG_HTML}}}
        else:
            mock_resp.json.return_value = {"parse": {"text": {"*": item_html}}}
        return mock_resp

    mock_get = mocker.patch("httpx.get", side_effect=mock_get_side_effect)

    result = wiki.get_page_html("Mirror", cache=cache_client)

    assert result == item_html
    assert mock_get.call_count == 2


def test_get_page_html_no_redirect_for_normal_page(mocker, cache_client: CacheClient):
    normal_html = "<p>Normal item page</p>"
    mock_get = mocker.patch("httpx.get")
    mock_get.return_value.json.return_value = {"parse": {"text": {"*": normal_html}}}
    mock_get.return_value.raise_for_status = lambda: None

    result = wiki.get_page_html("Normal Item", cache=cache_client)

    assert result == normal_html
    assert mock_get.call_count == 1


def test_get_page_html_caches_both_names_on_redirect(mocker, cache_client: CacheClient):
    item_html = "<p>Mirror is a crafting material...</p>"
    call_count = 0

    def mock_get_side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        mock_resp = mocker.MagicMock()
        mock_resp.raise_for_status = lambda: None
        if call_count == 1:
            mock_resp.json.return_value = {"parse": {"text": {"*": _DISAMBIG_HTML}}}
        else:
            mock_resp.json.return_value = {"parse": {"text": {"*": item_html}}}
        return mock_resp

    mock_get = mocker.patch("httpx.get", side_effect=mock_get_side_effect)

    wiki.get_page_html("Mirror", cache=cache_client)

    assert cache_client.get_wiki_page("Mirror") == item_html
    assert cache_client.get_wiki_page("Mirror (item)") == item_html

    result = wiki.get_page_html("Mirror", cache=cache_client)
    assert result == item_html
    assert mock_get.call_count == 2


def test_get_page_html_uses_cached_redirect_target(mocker, cache_client: CacheClient):
    item_html = "<p>Mirror is a crafting material...</p>"
    cache_client.set_wiki_page("Mirror (item)", item_html)

    mock_get = mocker.patch("httpx.get")
    mock_get.return_value.json.return_value = {"parse": {"text": {"*": _DISAMBIG_HTML}}}
    mock_get.return_value.raise_for_status = lambda: None

    result = wiki.get_page_html("Mirror", cache=cache_client)

    assert result == item_html
    assert mock_get.call_count == 1
    assert cache_client.get_wiki_page("Mirror") == item_html
    assert cache_client.get_wiki_page("Mirror (item)") == item_html
