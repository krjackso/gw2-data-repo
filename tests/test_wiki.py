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
    def test_small_html_without_excluded_sections_returned_unchanged(self):
        html = "<p>Small page with no excluded sections</p>"
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

    def test_contained_in_preserved_while_map_bonus_excluded(self):
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
        assert "Container list" in result
        assert "Map reward info" not in result
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

    def test_medium_html_filters_used_in_but_keeps_contained_in(self):
        html = (
            '<h2><span id="Acquisition">Acquisition</span></h2>'
            "<p>Get from vendor or salvage</p>"
            '<h3><span id="Contained_in">Contained in</span></h3>'
            "<p>Pile of Silky Sand (chance)</p>"
            '<h2><span id="Used_in">Used in</span></h2>'
            '<h3><span id="Weaponsmith">Weaponsmith</span></h3>'
            "<p>" + "x" * 50_000 + "</p>"
            '<h3><span id="Scribe">Scribe</span></h3>'
            "<p>" + "y" * 50_000 + "</p>"
        )
        assert len(html) < 300_000
        result = wiki.extract_acquisition_sections(html)
        assert "Get from vendor or salvage" in result
        assert "Pile of Silky Sand" in result
        assert "Weaponsmith" not in result
        assert "Scribe" not in result
        assert "x" * 50_000 not in result
        assert "y" * 50_000 not in result
        assert len(result) < len(html)

    def test_used_in_kept_for_multi_rarity_pages(self):
        html = _make_large_html(
            [
                '<h2><span id="Variants">Variants</span></h2>',
                '<table class="equip craftvariants">',
                '<tr id="item1"><td>Ascended</td></tr>',
                '<tr id="item2"><td>Legendary</td></tr>',
                "</table>",
                '<h2><span id="Sold_by">Sold by</span></h2>',
                "<p>Vendor info</p>",
                '<h2><span id="Used_in">Used in</span></h2>',
                "<p>Upgrade recipe from Ascended to Legendary</p>",
            ]
        )
        result = wiki.extract_acquisition_sections(html)
        assert "Variants" in result
        assert "Vendor info" in result
        assert "Used_in" in result
        assert "Upgrade recipe from Ascended to Legendary" in result

    def test_used_in_excluded_for_single_rarity_pages(self):
        html = _make_large_html(
            [
                '<h2><span id="Acquisition">Acquisition</span></h2>',
                "<p>Crafting info</p>",
                '<h2><span id="Used_in">Used in</span></h2>',
                "<p>List of recipes where this item is an ingredient</p>",
            ]
        )
        result = wiki.extract_acquisition_sections(html)
        assert "Crafting info" in result
        assert "Used_in" not in result
        assert "List of recipes where this item is an ingredient" not in result


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

_SERVER_REDIRECT_HTML = (
    '<div class="redirectMsg">'
    "<p>Redirect to:</p>"
    '<ul class="redirectText">'
    '<li><a href="/wiki/Valkyrie_Bearkin_War_Helm_(heavy)" '
    'title="Valkyrie Bearkin War Helm (heavy)">Valkyrie Bearkin War Helm (heavy)</a></li>'
    "</ul>"
    "</div>"
)


# --- Server redirect detection tests ---


def test_find_server_redirect_detects_redirect():
    result = wiki._find_server_redirect(_SERVER_REDIRECT_HTML)
    assert result == "Valkyrie Bearkin War Helm (heavy)"


def test_find_server_redirect_not_present():
    html = "<p>Normal page content</p>"
    result = wiki._find_server_redirect(html)
    assert result is None


def test_find_server_redirect_malformed_no_redirecttext():
    html = '<div class="redirectMsg"><p>Redirect to:</p></div>'
    result = wiki._find_server_redirect(html)
    assert result is None


def test_find_server_redirect_malformed_no_href():
    html = (
        '<div class="redirectMsg">'
        "<p>Redirect to:</p>"
        '<ul class="redirectText">'
        "<li><a>Target Page</a></li>"
        "</ul>"
        "</div>"
    )
    result = wiki._find_server_redirect(html)
    assert result is None


def test_find_server_redirect_url_encoded():
    html = (
        '<div class="redirectMsg">'
        '<ul class="redirectText">'
        '<li><a href="/wiki/Item_%28heavy%29">Item (heavy)</a></li>'
        "</ul>"
        "</div>"
    )
    result = wiki._find_server_redirect(html)
    assert result == "Item (heavy)"


def test_find_server_redirect_replaces_underscores():
    html = (
        '<div class="redirectMsg">'
        '<ul class="redirectText">'
        '<li><a href="/wiki/Target_Page_Name">Target Page Name</a></li>'
        "</ul>"
        "</div>"
    )
    result = wiki._find_server_redirect(html)
    assert result == "Target Page Name"


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


def test_get_page_html_follows_server_redirect(mocker, cache_client: CacheClient):
    final_html = "<p>Heavy armor variant content...</p>"
    call_count = 0

    def mock_get_side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        mock_resp = mocker.MagicMock()
        mock_resp.raise_for_status = lambda: None
        if call_count == 1:
            mock_resp.json.return_value = {"parse": {"text": {"*": _SERVER_REDIRECT_HTML}}}
        else:
            mock_resp.json.return_value = {"parse": {"text": {"*": final_html}}}
        return mock_resp

    mock_get = mocker.patch("httpx.get", side_effect=mock_get_side_effect)

    result = wiki.get_page_html("Valkyrie Bearkin War Helm", cache=cache_client)

    assert result == final_html
    assert mock_get.call_count == 2


def test_get_page_html_caches_both_names_on_server_redirect(mocker, cache_client: CacheClient):
    final_html = "<p>Heavy armor variant content...</p>"
    call_count = 0

    def mock_get_side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        mock_resp = mocker.MagicMock()
        mock_resp.raise_for_status = lambda: None
        if call_count == 1:
            mock_resp.json.return_value = {"parse": {"text": {"*": _SERVER_REDIRECT_HTML}}}
        else:
            mock_resp.json.return_value = {"parse": {"text": {"*": final_html}}}
        return mock_resp

    mock_get = mocker.patch("httpx.get", side_effect=mock_get_side_effect)

    wiki.get_page_html("Valkyrie Bearkin War Helm", cache=cache_client)

    assert cache_client.get_wiki_page("Valkyrie Bearkin War Helm") == final_html
    assert cache_client.get_wiki_page("Valkyrie Bearkin War Helm (heavy)") == final_html

    result = wiki.get_page_html("Valkyrie Bearkin War Helm", cache=cache_client)
    assert result == final_html
    assert mock_get.call_count == 2


def test_get_page_html_server_redirect_chain(mocker, cache_client: CacheClient):
    redirect2_html = (
        '<div class="redirectMsg">'
        '<ul class="redirectText">'
        '<li><a href="/wiki/Final_Target">Final Target</a></li>'
        "</ul>"
        "</div>"
    )
    final_html = "<p>Final page content</p>"
    call_count = 0

    def mock_get_side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        mock_resp = mocker.MagicMock()
        mock_resp.raise_for_status = lambda: None
        if call_count == 1:
            mock_resp.json.return_value = {"parse": {"text": {"*": _SERVER_REDIRECT_HTML}}}
        elif call_count == 2:
            mock_resp.json.return_value = {"parse": {"text": {"*": redirect2_html}}}
        else:
            mock_resp.json.return_value = {"parse": {"text": {"*": final_html}}}
        return mock_resp

    mock_get = mocker.patch("httpx.get", side_effect=mock_get_side_effect)

    result = wiki.get_page_html("Start Page", cache=cache_client)

    assert result == final_html
    assert mock_get.call_count == 3


def test_get_page_html_redirect_depth_limit(mocker, cache_client: CacheClient):
    def mock_get_side_effect(*args, **kwargs):
        mock_resp = mocker.MagicMock()
        mock_resp.raise_for_status = lambda: None
        mock_resp.json.return_value = {"parse": {"text": {"*": _SERVER_REDIRECT_HTML}}}
        return mock_resp

    mocker.patch("httpx.get", side_effect=mock_get_side_effect)

    with pytest.raises(WikiError, match="Redirect chain exceeded max depth"):
        wiki.get_page_html("Loop Start", cache=cache_client)


def test_server_redirect_priority_over_disambiguation(mocker, cache_client: CacheClient):
    mixed_html = _SERVER_REDIRECT_HTML + _DISAMBIG_HTML
    final_html = "<p>Server redirect target</p>"
    call_count = 0

    def mock_get_side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        mock_resp = mocker.MagicMock()
        mock_resp.raise_for_status = lambda: None
        if call_count == 1:
            mock_resp.json.return_value = {"parse": {"text": {"*": mixed_html}}}
        else:
            mock_resp.json.return_value = {"parse": {"text": {"*": final_html}}}
        return mock_resp

    mocker.patch("httpx.get", side_effect=mock_get_side_effect)

    result = wiki.get_page_html("Test Page", cache=cache_client)

    assert result == final_html
    assert cache_client.get_wiki_page("Test Page") == final_html
    assert cache_client.get_wiki_page("Valkyrie Bearkin War Helm (heavy)") == final_html


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
