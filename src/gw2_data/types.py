"""
Type definitions for GW2 API responses.

Provides TypedDict structures matching the GW2 API schema to enable
strict type checking and better IDE support.
"""

from typing import NamedTuple, NotRequired, TypedDict

from gw2_data.models import ItemRarity, ItemType


class GW2Item(TypedDict):
    id: int
    name: str
    type: ItemType
    rarity: ItemRarity
    level: int
    vendor_value: NotRequired[int]
    icon: NotRequired[str]
    description: NotRequired[str]
    flags: NotRequired[list[str]]


class RecipeIngredient(TypedDict):
    item_id: int
    count: int


class GW2Recipe(TypedDict):
    id: int
    type: str
    output_item_id: int
    output_item_count: int
    min_rating: int
    disciplines: list[str]
    ingredients: list[RecipeIngredient]
    flags: NotRequired[list[str]]


class BulkResult(NamedTuple):
    items: list[GW2Item]
    from_cache: bool
