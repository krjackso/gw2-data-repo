"""Tests for vendor_scraper module — HTML parsing for vendor/location data."""

from gw2_data.vendor_scraper import (
    compute_chat_link,
    extract_area_waypoints,
    extract_vendor_locations,
)

# ---------------------------------------------------------------------------
# compute_chat_link
# ---------------------------------------------------------------------------


class TestComputeChatLink:
    def test_map_type_known_waypoint(self):
        result = compute_chat_link("map", 634)
        assert result == "[&BHoCAAA=]"

    def test_map_type_id_zero(self):
        result = compute_chat_link("map", 0)
        assert result == "[&BAAAAAA=]"

    def test_unknown_type_returns_none(self):
        result = compute_chat_link("skill", 1234)
        assert result is None

    def test_map_type_large_id(self):
        result = compute_chat_link("map", 1699)
        assert result is not None
        assert result.startswith("[&")
        assert result.endswith("]")


# ---------------------------------------------------------------------------
# extract_vendor_locations — infobox single location (Rojan-style)
# ---------------------------------------------------------------------------

_ROJAN_HTML = """
<div class="mw-parser-output">
<div class="infobox npc">
<dl>
  <dt><a href="/wiki/Location" title="Location">Location</a></dt>
  <dd><a href="/wiki/Earthshake_Basin" title="Earthshake Basin">Earthshake Basin</a>
    <br /><small>(<a href="/wiki/Frostgorge_Sound" title="Frostgorge Sound">Frostgorge Sound</a>)</small>
  </dd>
</dl>
</div>
</div>
"""

_MIYANI_HTML = """
<div class="mw-parser-output">
<div class="infobox npc">
<dl>
  <dt><a href="/wiki/Location" title="Location">Locations</a></dt>
  <dd>
    <ul>
      <li>
        <a href="/wiki/Trader%27s_Forum" title="Trader's Forum">Trader's Forum</a>
        <br /><small>(<a href="/wiki/Lion%27s_Arch" title="Lion's Arch">Lion's Arch</a>)</small>
      </li>
      <li>
        <a href="/wiki/Trader%27s_Forum_(Memory_of_Old_Lion%27s_Arch)" title="Trader's Forum (Memory of Old Lion's Arch)">Trader's Forum</a>
        <br /><small>(<a href="/wiki/Memory_of_Old_Lion%27s_Arch" title="Memory of Old Lion's Arch">Memory of Old Lion's Arch</a>)</small>
      </li>
    </ul>
  </dd>
</dl>
</div>
</div>
"""

_DUGAN_HTML = """
<div class="mw-parser-output">
<div class="infobox npc">
<dl>
  <dt><a href="/wiki/Location" title="Location">Location</a></dt>
  <dd>
    <a href="/wiki/World_vs._World" title="World vs. World">World vs. World</a>
    <br /><small>(<a href="/wiki/The_Mists" title="The Mists">The Mists</a>)</small>
  </dd>
</dl>
</div>
<h2><span class="mw-headline" id="Locations">Locations</span></h2>
<dl>
  <dt><a href="/wiki/The_Mists" title="The Mists">The Mists</a></dt>
</dl>
<ul>
  <li><a href="/wiki/Armistice_Bastion" title="Armistice Bastion">Armistice Bastion</a></li>
  <li><a href="/wiki/Blue_Alpine_Borderlands" title="Blue Alpine Borderlands">Blue Alpine Borderlands</a>
    <ul>
      <li><a href="/wiki/Blue_World_Citadel" title="Blue World Citadel">Blue World Citadel</a></li>
      <li><a href="/wiki/Green_World_Border_(Blue_Borderlands)" title="Green World Border (Blue Borderlands)">Green World Border</a></li>
    </ul>
  </li>
</ul>
</div>
"""

_NO_LOCATION_HTML = """
<div class="mw-parser-output">
<div class="infobox npc">
<dl>
  <dt><a href="/wiki/Race">Race</a></dt>
  <dd>Human</dd>
</dl>
</div>
</div>
"""


class TestExtractVendorLocations:
    def test_single_infobox_location(self):
        result = extract_vendor_locations(_ROJAN_HTML)
        assert len(result) == 1
        loc = result[0]
        assert loc.name == "Earthshake Basin"
        assert loc.wiki_page == "Earthshake Basin"
        assert loc.zone == "Frostgorge Sound"
        assert loc.zone_wiki_page == "Frostgorge Sound"

    def test_multiple_infobox_locations_via_ul(self):
        result = extract_vendor_locations(_MIYANI_HTML)
        assert len(result) == 2
        names = [r.name for r in result]
        assert "Trader's Forum" in names
        pages = [r.wiki_page for r in result]
        assert "Trader's Forum" in pages
        assert "Trader's Forum (Memory of Old Lion's Arch)" in pages
        zones = [r.zone for r in result]
        assert "Lion's Arch" in zones
        assert "Memory of Old Lion's Arch" in zones

    def test_body_locations_section_overrides_generic_infobox(self):
        result = extract_vendor_locations(_DUGAN_HTML)
        names = [r.name for r in result]
        assert "Armistice Bastion" in names
        assert "Blue World Citadel" in names
        assert "Green World Border" in names
        assert "World vs. World" not in names

    def test_body_locations_nested_zone_assigned(self):
        result = extract_vendor_locations(_DUGAN_HTML)
        citadel = next(r for r in result if r.name == "Blue World Citadel")
        assert citadel.zone == "Blue Alpine Borderlands"

    def test_no_location_returns_empty(self):
        result = extract_vendor_locations(_NO_LOCATION_HTML)
        assert result == []

    def test_empty_html_returns_empty(self):
        result = extract_vendor_locations("<html></html>")
        assert result == []

    def test_wiki_page_url_decoded(self):
        result = extract_vendor_locations(_MIYANI_HTML)
        pages = [r.wiki_page for r in result]
        assert "Trader's Forum" in pages


# ---------------------------------------------------------------------------
# extract_area_waypoints
# ---------------------------------------------------------------------------

_EARTHSHAKE_HTML = """
<div class="mw-parser-output">
<h2><span id="Points_of_interest">Points of interest</span></h2>
<dl>
  <dt>Waypoints</dt>
  <dd>
    <span id="Earthshake&#95;Waypoint"></span>
    <span class="inline-icon"><a href="/wiki/Waypoint" title="Waypoint"><img alt="Waypoint icon" /></a></span>
    Earthshake Waypoint &#8212;
    <span class="gamelink" id="gamelink-1" data-type="map" data-id="634" title="634"></span>
  </dd>
</dl>
</div>
"""

_MULTIPLE_WAYPOINTS_HTML = """
<div class="mw-parser-output">
<dl>
  <dt>Waypoints</dt>
  <dd>
    <span id="First&#95;Waypoint"></span>
    <span class="inline-icon"><a href="/wiki/Waypoint"><img /></a></span>
    First Waypoint &#8212;
    <span class="gamelink" data-type="map" data-id="100" title="100"></span>
    <br />
    <span id="Second&#95;Waypoint"></span>
    <span class="inline-icon"><a href="/wiki/Waypoint"><img /></a></span>
    Second Waypoint &#8212;
    <span class="gamelink" data-type="map" data-id="200" title="200"></span>
  </dd>
</dl>
</div>
"""

_NO_WAYPOINTS_HTML = """
<div class="mw-parser-output">
<dl>
  <dt>Points of interest</dt>
  <dd>Some POI</dd>
</dl>
</div>
"""


class TestExtractAreaWaypoints:
    def test_extracts_single_waypoint(self):
        result = extract_area_waypoints(_EARTHSHAKE_HTML)
        assert len(result) == 1
        assert result[0].name == "Earthshake Waypoint"
        assert result[0].chat_link == "[&BHoCAAA=]"

    def test_extracts_all_waypoints(self):
        result = extract_area_waypoints(_MULTIPLE_WAYPOINTS_HTML)
        assert len(result) == 2
        assert result[0].name == "First Waypoint"
        assert result[0].chat_link == compute_chat_link("map", 100)
        assert result[1].name == "Second Waypoint"
        assert result[1].chat_link == compute_chat_link("map", 200)

    def test_returns_empty_when_no_waypoints_section(self):
        result = extract_area_waypoints(_NO_WAYPOINTS_HTML)
        assert result == []

    def test_returns_empty_for_empty_html(self):
        result = extract_area_waypoints("<html></html>")
        assert result == []

    def test_chat_link_format(self):
        result = extract_area_waypoints(_EARTHSHAKE_HTML)
        assert len(result) == 1
        assert result[0].chat_link.startswith("[&")
        assert result[0].chat_link.endswith("]")
