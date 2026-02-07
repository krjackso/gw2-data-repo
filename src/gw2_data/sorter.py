"""
Acquisition and requirement sorting for deterministic YAML output.

Sorts acquisitions by type priority, then by type-specific metadata fields,
then by discontinued status, and finally by output quantity. Also sorts
requirements within each acquisition by ID for maximum diff stability.

Configuration-driven design allows easy modification of sort priorities by
updating ACQUISITION_TYPE_ORDER and ACQUISITION_SORT_FIELDS constants.
"""

from typing import Any

# Acquisition type order: most direct/deterministic methods first
# (crafting, mystic_forge, vendor) → gameplay methods (achievement, container)
# → region/track methods (map_reward, wvw_reward) → seasonal (wizards_vault, story)
ACQUISITION_TYPE_ORDER = [
    "crafting",
    "mystic_forge",
    "vendor",
    "achievement",
    "container",
    "salvage",
    "map_reward",
    "wvw_reward",
    "pvp_reward",
    "wizards_vault",
    "story",
]

# Secondary sort keys per type (ordered list of dot-notation field paths)
# Uses dot notation: "metadata.minRating" for nested fields
# Array indices use brackets: "metadata.disciplines[0]" for first element
# All sorting is ascending; boolean fields (guaranteed, seasonal) are negated
# in _get_sort_key() to achieve True-first sorting (since False < True in Python)
ACQUISITION_SORT_FIELDS = {
    "crafting": [
        "metadata.minRating",
        "metadata.disciplines[0]",
    ],
    "mystic_forge": [],
    "vendor": [
        "vendorName",
    ],
    "achievement": [
        "metadata.achievementName",
    ],
    "container": [
        "metadata.guaranteed",
        "metadata.containerItemId",
    ],
    "salvage": [
        "metadata.guaranteed",
        "metadata.sourceItemId",
    ],
    "map_reward": [
        "metadata.rewardType",
        "metadata.regionName",
    ],
    "wvw_reward": [
        "metadata.trackName",
    ],
    "pvp_reward": [
        "metadata.trackName",
    ],
    "wizards_vault": [
        "metadata.seasonal",
    ],
    "story": [
        "metadata.expansion",
        "metadata.storyChapter",
    ],
}


def sort_acquisitions(acquisitions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Sort acquisitions deterministically by type, metadata, discontinued status, and output quantity.
    Also sorts requirements within each acquisition.
    """
    sorted_acqs = []
    for acq in acquisitions:
        acq_copy = acq.copy()
        if "requirements" in acq_copy:
            acq_copy["requirements"] = sort_requirements(acq_copy["requirements"])
        sorted_acqs.append(acq_copy)

    return sorted(sorted_acqs, key=_get_sort_key)


def sort_requirements(requirements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Sort requirements by ID: items first (by itemId), then currencies (by currencyId).
    """

    def req_sort_key(req: dict[str, Any]) -> tuple[int, int]:
        req_type = 0 if "itemId" in req else 1
        req_id = req.get("itemId", req.get("currencyId", 0))
        return (req_type, req_id)

    return sorted(requirements, key=req_sort_key)


def _parse_field_path(path: str) -> list[str | int]:
    """
    Parse dot notation path with array indices into list of keys.

    Examples:
        "metadata.minRating" -> ["metadata", "minRating"]
        "metadata.disciplines[0]" -> ["metadata", "disciplines", 0]
    """
    parts: list[str | int] = []
    for segment in path.split("."):
        if "[" in segment:
            field, idx = segment.split("[")
            parts.append(field)
            parts.append(int(idx.rstrip("]")))
        else:
            parts.append(segment)
    return parts


def _extract_field_value(data: dict[str, Any], field_path: str) -> Any:
    """Navigate nested dict/list to extract a field value using dot notation."""
    value: Any = data
    for key in _parse_field_path(field_path):
        if isinstance(value, dict):
            value = value.get(key)
        elif isinstance(value, list) and isinstance(key, int):
            value = value[key] if key < len(value) else None
        else:
            return None

        if value is None:
            return None

    return value


def _get_sort_key(acq: dict[str, Any]) -> tuple[int, tuple[Any, ...], int, int]:
    """Extract compound sort key from acquisition for deterministic ordering."""
    acq_type = acq["type"]

    try:
        type_priority = ACQUISITION_TYPE_ORDER.index(acq_type)
    except ValueError:
        type_priority = 999

    secondary_values = []
    for field_path in ACQUISITION_SORT_FIELDS.get(acq_type, []):
        value = _extract_field_value(acq, field_path)

        if value is None:
            value = ""

        if field_path in ["metadata.guaranteed", "metadata.seasonal"] and isinstance(value, bool):
            value = not value

        secondary_values.append(value)

    discontinued = 1 if acq.get("discontinued") else 0
    output_qty = acq.get("outputQuantity", 1)

    return (type_priority, tuple(secondary_values), discontinued, output_qty)
