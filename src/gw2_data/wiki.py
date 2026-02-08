"""
GW2 Wiki client for fetching item documentation.

Wraps the GW2 Wiki MediaWiki API to fetch rendered HTML pages containing
acquisition information. All pages are cached indefinitely to minimize
load on the wiki servers.
"""

import logging
import re

import httpx

from gw2_data.cache import CacheClient
from gw2_data.config import get_settings
from gw2_data.exceptions import WikiError

log = logging.getLogger(__name__)

_WIKI_API_URL = "https://wiki.guildwars2.com/api.php"
_MAX_HTML_LENGTH = 200_000


def get_page_html(page_name: str, cache: CacheClient) -> str:
    if not page_name or not page_name.strip():
        raise WikiError("Page name cannot be empty")

    cached = cache.get_wiki_page(page_name)
    if cached is not None:
        log.info("Wiki page '%s': using cached HTML", page_name)
        return cached

    log.info("Wiki page '%s': fetching from wiki API", page_name)
    settings = get_settings()
    try:
        response = httpx.get(
            _WIKI_API_URL,
            params={
                "action": "parse",
                "page": page_name,
                "prop": "text",
                "format": "json",
            },
            timeout=settings.api_timeout,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise WikiError(
            f"Failed to fetch wiki page '{page_name}': HTTP {e.response.status_code}"
        ) from e
    except httpx.RequestError as e:
        raise WikiError(f"Network error fetching wiki page '{page_name}': {e}") from e

    try:
        data = response.json()
    except Exception as e:
        raise WikiError(f"Invalid JSON response for wiki page '{page_name}'") from e

    if "error" in data:
        error_info = data["error"].get("info", "Unknown error")
        raise WikiError(f"Wiki page '{page_name}' not found: {error_info}")

    if "parse" not in data or "text" not in data["parse"]:
        raise WikiError(f"Unexpected wiki API response format for '{page_name}'")

    html_content: str = data["parse"]["text"]["*"]
    cache.set_wiki_page(page_name, html_content)
    return html_content


def extract_acquisition_sections(html: str) -> str:
    """
    Extract only acquisition-relevant sections from wiki HTML.

    Reduces HTML size for LLM processing by removing irrelevant sections
    (Dropped by, Used in, Contained in, Currency for, etc.) while keeping
    core acquisition information (Acquisition, Sold by, Vendor, Recipe, etc.).

    For commonly used items, "Contained in" and "Currency for" sections can be
    massive (hundreds of KB), listing every recipe/container that outputs this
    item or every vendor that accepts it as currency. We exclude these since
    the LLM should focus on direct acquisition methods, not reverse dependencies.

    If the result is still too large, truncates to _MAX_HTML_LENGTH characters.
    """
    if len(html) <= _MAX_HTML_LENGTH:
        return html

    excluded_sections = [
        r'<span[^>]*id="Dropped_by"[^>]*>.*?(?=<h[12]|$)',
        r'<span[^>]*id="Contained_in"[^>]*>.*?(?=<h[12]|$)',
        r'<span[^>]*id="Used_in"[^>]*>.*?(?=<h[12]|$)',
        r'<span[^>]*id="Currency_for"[^>]*>.*?(?=<h[12]|$)',
        r'<span[^>]*id="Recipe_sheet"[^>]*>.*?(?=<h[12]|$)',
        r'<span[^>]*id="Salvage_results"[^>]*>.*?(?=<h[12]|$)',
        r'<span[^>]*id="Trivia"[^>]*>.*?(?=<h[12]|$)',
        r'<span[^>]*id="Gallery"[^>]*>.*?(?=<h[12]|$)',
        r'<span[^>]*id="Notes"[^>]*>.*?(?=<h[12]|$)',
        r'<span[^>]*id="External_links"[^>]*>.*?(?=<h[12]|$)',
    ]

    filtered_html = html
    for pattern in excluded_sections:
        filtered_html = re.sub(pattern, "", filtered_html, flags=re.DOTALL | re.IGNORECASE)

    if len(filtered_html) > _MAX_HTML_LENGTH:
        log.warning(
            "Filtered HTML still too large (%d chars), truncating to %d",
            len(filtered_html),
            _MAX_HTML_LENGTH,
        )
        filtered_html = filtered_html[:_MAX_HTML_LENGTH]

    log.info("Filtered acquisition HTML: %d chars (from %d)", len(filtered_html), len(html))
    return filtered_html
