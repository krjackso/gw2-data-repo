"""
HTML parsing for GW2 wiki vendor and location data.

Extracts structured location data from NPC vendor pages and waypoint
chat links from area pages. Uses BeautifulSoup for reliable HTML parsing
of the MediaWiki-rendered output.

Two primary extraction targets:
- Vendor NPC pages: location area name + zone name from infobox or Locations section
- Area pages: first waypoint name + game link chat code from POI list
"""

from __future__ import annotations

import base64
import logging
import struct
from dataclasses import dataclass
from html import unescape
from urllib.parse import unquote

from bs4 import BeautifulSoup, Tag

log = logging.getLogger(__name__)

_WIKI_BASE_URL = "https://wiki.guildwars2.com/wiki/"

# GW2 chat link type bytes by data-type attribute value
_CHAT_LINK_TYPE_BYTES: dict[str, int] = {
    "map": 0x04,
}


@dataclass
class AreaRef:
    name: str
    wiki_page: str
    zone: str
    zone_wiki_page: str


@dataclass
class WaypointData:
    name: str
    chat_link: str


def compute_chat_link(data_type: str, data_id: int) -> str | None:
    type_byte = _CHAT_LINK_TYPE_BYTES.get(data_type)
    if type_byte is None:
        log.warning("Unknown chat link data-type: %s", data_type)
        return None
    payload = struct.pack("<BI", type_byte, data_id)
    encoded = base64.b64encode(payload).decode("ascii")
    return f"[&{encoded}]"


def _href_to_page_name(href: str) -> str:
    path = href.removeprefix("/wiki/")
    return unescape(unquote(path)).replace("_", " ")


def extract_vendor_locations(html: str) -> list[AreaRef]:
    soup = BeautifulSoup(html, "html.parser")
    locations = _extract_body_locations(soup)
    if not locations:
        locations = _extract_infobox_locations(soup)
    return locations


def _extract_infobox_locations(soup: BeautifulSoup) -> list[AreaRef]:
    infobox = soup.find("div", class_="infobox")
    if not infobox or not isinstance(infobox, Tag):
        return []

    for dt in infobox.find_all("dt"):
        dt_text = dt.get_text(strip=True)
        if dt_text not in ("Location", "Locations"):
            continue
        dd = dt.find_next_sibling("dd")
        if not dd or not isinstance(dd, Tag):
            continue

        ul = dd.find("ul")
        if ul and isinstance(ul, Tag):
            return _parse_location_list_items(ul.find_all("li", recursive=False))

        area_link = dd.find("a")
        if not area_link or not isinstance(area_link, Tag):
            continue
        area_href = area_link.get("href", "")
        area_name = area_link.get_text(strip=True)
        area_page = _href_to_page_name(str(area_href))

        small = dd.find("small")
        zone_name = ""
        zone_page = ""
        if small and isinstance(small, Tag):
            zone_link = small.find("a")
            if zone_link and isinstance(zone_link, Tag):
                zone_name = zone_link.get_text(strip=True)
                zone_page = _href_to_page_name(str(zone_link.get("href", "")))

        return [
            AreaRef(name=area_name, wiki_page=area_page, zone=zone_name, zone_wiki_page=zone_page)
        ]

    return []


def _parse_location_list_items(items: list[Tag]) -> list[AreaRef]:
    results: list[AreaRef] = []
    for li in items:
        area_link = li.find("a", recursive=False)
        if not area_link or not isinstance(area_link, Tag):
            continue
        area_name = area_link.get_text(strip=True)
        area_page = _href_to_page_name(str(area_link.get("href", "")))

        small = li.find("small", recursive=False)
        zone_name = ""
        zone_page = ""
        if small and isinstance(small, Tag):
            zone_link = small.find("a")
            if zone_link and isinstance(zone_link, Tag):
                zone_name = zone_link.get_text(strip=True)
                zone_page = _href_to_page_name(str(zone_link.get("href", "")))

        results.append(
            AreaRef(name=area_name, wiki_page=area_page, zone=zone_name, zone_wiki_page=zone_page)
        )
    return results


def _extract_body_locations(soup: BeautifulSoup) -> list[AreaRef]:
    locations_span = soup.find("span", id="Locations")
    if not locations_span or not isinstance(locations_span, Tag):
        return []

    results: list[AreaRef] = []
    heading = locations_span.find_parent(["h2", "h3"])
    if not heading:
        return []

    current_zone = ""
    current_zone_page = ""
    for sibling in heading.next_siblings:
        if not isinstance(sibling, Tag):
            continue
        if sibling.name in ("h2", "h3") and sibling != heading:
            break

        if sibling.name == "dl":
            dt = sibling.find("dt")
            if dt and isinstance(dt, Tag):
                zone_link = dt.find("a")
                if zone_link and isinstance(zone_link, Tag):
                    current_zone = zone_link.get_text(strip=True)
                    current_zone_page = _href_to_page_name(str(zone_link.get("href", "")))
                else:
                    current_zone = dt.get_text(strip=True)
                    current_zone_page = ""

        if sibling.name == "ul":
            results.extend(_extract_leaf_areas_from_ul(sibling, current_zone, current_zone_page))

    return results


def _extract_leaf_areas_from_ul(ul: Tag, zone: str, zone_page: str) -> list[AreaRef]:
    results: list[AreaRef] = []
    for li in ul.find_all("li", recursive=False):
        nested_ul = li.find("ul")
        if nested_ul and isinstance(nested_ul, Tag):
            nested_zone_link = li.find("a", recursive=False)
            nested_zone = zone
            nested_zone_page = zone_page
            if nested_zone_link and isinstance(nested_zone_link, Tag):
                nested_zone = nested_zone_link.get_text(strip=True)
                nested_zone_page = _href_to_page_name(str(nested_zone_link.get("href", "")))
            results.extend(_extract_leaf_areas_from_ul(nested_ul, nested_zone, nested_zone_page))
        else:
            area_link = li.find("a")
            if area_link and isinstance(area_link, Tag):
                area_name = area_link.get_text(strip=True)
                area_page = _href_to_page_name(str(area_link.get("href", "")))
                results.append(
                    AreaRef(
                        name=area_name,
                        wiki_page=area_page,
                        zone=zone,
                        zone_wiki_page=zone_page,
                    )
                )
    return results


def extract_area_waypoint(html: str) -> WaypointData | None:
    soup = BeautifulSoup(html, "html.parser")

    waypoints_dt = None
    for dt in soup.find_all("dt"):
        if dt.get_text(strip=True) == "Waypoints":
            waypoints_dt = dt
            break

    if not waypoints_dt or not isinstance(waypoints_dt, Tag):
        return None

    dd = waypoints_dt.find_next_sibling("dd")
    if not dd or not isinstance(dd, Tag):
        return None

    return _parse_first_waypoint_from_dd(dd)


def _parse_first_waypoint_from_dd(dd: Tag) -> WaypointData | None:
    gamelink = dd.find("span", class_="gamelink")
    if not gamelink or not isinstance(gamelink, Tag):
        return None

    data_type = str(gamelink.get("data-type", ""))
    data_id_str = str(gamelink.get("data-id", ""))
    if not data_type or not data_id_str:
        return None

    try:
        data_id = int(data_id_str)
    except ValueError:
        log.warning("Invalid gamelink data-id: %s", data_id_str)
        return None

    chat_link = compute_chat_link(data_type, data_id)
    if chat_link is None:
        return None

    name = _extract_waypoint_name(dd, gamelink)
    if not name:
        log.warning("Could not extract waypoint name")
        return None

    return WaypointData(name=name, chat_link=chat_link)


def _extract_waypoint_name(dd: Tag, gamelink: Tag) -> str | None:
    anchor_span = dd.find("span", id=lambda x: x and x.endswith("_Waypoint"))
    if anchor_span and isinstance(anchor_span, Tag):
        span_id = str(anchor_span.get("id", ""))
        return unescape(span_id).replace("_", " ")

    text_before = gamelink.previous_sibling
    if text_before:
        text = str(text_before).strip().strip("—").strip()
        if "Waypoint" in text:
            return text

    return None
