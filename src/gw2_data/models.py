"""Pydantic models for GW2 acquisition data."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field

# --- Acquisition Types ---

AcquisitionType = Literal[
    "crafting",
    "mystic_forge",
    "vendor",
    "trading_post",
    "achievement",
    "map_reward",
    "container",
    "salvage",
    "wvw_reward",
    "pvp_reward",
    "wizards_vault",
    "story",
]


# --- Requirements ---


class ItemRequirement(BaseModel):
    type: Literal["item"]
    item_id: int = Field(alias="itemId")
    name: str
    quantity: int = Field(ge=1)


class CurrencyRequirement(BaseModel):
    type: Literal["currency"]
    currency_id: int = Field(alias="currencyId")
    name: str
    quantity: int = Field(ge=1)


class UnresolvedRequirement(BaseModel):
    type: Literal["unresolved"]
    name: str
    quantity: int = Field(ge=1)


AcquisitionRequirement = Annotated[
    ItemRequirement | CurrencyRequirement | UnresolvedRequirement,
    Field(discriminator="type"),
]


# --- Metadata ---


class RecipeMetadata(BaseModel):
    recipe_type: str = Field(alias="recipeType")
    disciplines: list[str] | None = None
    min_rating: int | None = Field(default=None, alias="minRating")
    recipe_sheet: str | None = Field(default=None, alias="recipeSheet")


class VendorMetadata(BaseModel):
    vendor_name: str = Field(alias="vendorName")
    vendor_location: str | None = Field(default=None, alias="vendorLocation")
    map_id: int | None = Field(default=None, alias="mapId")


class VendorLimitMetadata(BaseModel):
    limit_type: Literal["daily", "weekly", "season", "lifetime"] = Field(alias="limitType")
    limit_amount: int = Field(alias="limitAmount")


class AchievementMetadata(BaseModel):
    achievement_id: int | None = Field(default=None, alias="achievementId")
    achievement_name: str = Field(alias="achievementName")
    achievement_category: str | None = Field(default=None, alias="achievementCategory")
    description: str | None = None
    wiki_url: str | None = Field(default=None, alias="wikiUrl")
    repeatable: bool = False
    time_gated: bool = Field(default=False, alias="timeGated")


class ContainerMetadata(BaseModel):
    container_item_id: int = Field(alias="containerItemId")
    container_name: str = Field(alias="containerName")
    guaranteed: bool | None = None


class SalvageMetadata(BaseModel):
    source_item_id: int | None = Field(default=None, alias="sourceItemId")
    source_item_name: str = Field(alias="sourceItemName")
    guaranteed: bool


class RewardTrackMetadata(BaseModel):
    track_name: str = Field(alias="trackName")
    track_type: Literal["wvw", "pvp"] = Field(alias="trackType")
    wiki_url: str = Field(alias="wikiUrl")


class MapRewardMetadata(BaseModel):
    reward_type: Literal["world_completion", "region_completion", "map_completion"] = Field(
        alias="rewardType"
    )
    region_name: str = Field(alias="regionName")
    estimated_hours: dict[str, float] = Field(alias="estimatedHours")
    wiki_url: str = Field(alias="wikiUrl")
    notes: str | None = None


class WizardsVaultMetadata(BaseModel):
    cost: int
    currency_name: str = Field(default="Astral Acclaim", alias="currencyName")
    seasonal: bool = False


class StoryMetadata(BaseModel):
    story_chapter: str | None = Field(default=None, alias="storyChapter")
    expansion: str | None = None


# --- Acquisition ---


class Acquisition(BaseModel):
    type: AcquisitionType
    output_quantity: int = Field(default=1, ge=1, alias="outputQuantity")
    requirements: list[AcquisitionRequirement] = Field(default_factory=list)
    metadata: dict | None = None

    model_config = {"populate_by_name": True}


# --- Top-Level File ---


class AcquisitionFile(BaseModel):
    item_id: int = Field(alias="itemId")
    item_name: str = Field(alias="itemName")
    wiki_url: str | None = Field(default=None, alias="wikiUrl")
    last_updated: str = Field(alias="lastUpdated")
    acquisitions: list[Acquisition]

    model_config = {"populate_by_name": True}
