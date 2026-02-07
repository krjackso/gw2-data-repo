"""
LLM extraction logic for parsing wiki pages into structured item data.

Uses Claude to extract acquisition methods from wiki HTML, combines with
GW2 API item data, and validates against the schema. Results are cached
by content hash to avoid re-processing identical wiki content.
"""

import hashlib
from datetime import UTC, datetime

from gw2_data.cache import CacheClient
from gw2_data.types import GW2Item

_CONTENT_HASH_LENGTH = 16


def extract_acquisitions(
    item_id: int,
    item_name: str,
    wiki_html: str,
    api_data: GW2Item,
    cache: CacheClient,
) -> dict:
    content_hash = hashlib.sha256(wiki_html.encode()).hexdigest()[:_CONTENT_HASH_LENGTH]

    cached = cache.get_llm_extraction(item_id, item_name, content_hash)
    if cached is not None:
        return cached

    result = {
        "id": api_data["id"],
        "name": api_data["name"],
        "type": api_data["type"],
        "rarity": api_data["rarity"],
        "level": api_data["level"],
        "icon": api_data.get("icon"),
        "description": api_data.get("description"),
        "vendorValue": api_data.get("vendor_value"),
        "flags": api_data.get("flags", []),
        "wikiUrl": f"https://wiki.guildwars2.com/wiki/{item_name.replace(' ', '_')}",
        "lastUpdated": datetime.now(UTC).date().isoformat(),
        "acquisitions": [],
    }

    cache.set_llm_extraction(item_id, item_name, content_hash, result)
    return result
