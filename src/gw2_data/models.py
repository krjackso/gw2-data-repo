"""Pydantic models for GW2 item data with acquisition methods."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field

# --- GW2 API Enums ---

ItemType = Literal[
    "Armor",
    "Back",
    "Bag",
    "Consumable",
    "Container",
    "CraftingMaterial",
    "Gathering",
    "Gizmo",
    "JadeTechModule",
    "Key",
    "MiniPet",
    "PowerCore",
    "Relic",
    "Tool",
    "Trait",
    "Trinket",
    "Trophy",
    "UpgradeComponent",
    "Weapon",
]

ItemRarity = Literal[
    "Junk",
    "Basic",
    "Fine",
    "Masterwork",
    "Rare",
    "Exotic",
    "Ascended",
    "Legendary",
]

# --- Acquisition Types ---

AcquisitionType = Literal[
    "crafting",
    "mystic_forge",
    "vendor",
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
    item_id: int = Field(alias="itemId", gt=0)
    quantity: int = Field(ge=1)


class CurrencyRequirement(BaseModel):
    currency_id: int = Field(alias="currencyId", gt=0)
    quantity: int = Field(ge=1)


AcquisitionRequirement = Annotated[
    ItemRequirement | CurrencyRequirement,
    Field(discriminator=None),
]


# --- Metadata ---


class RecipeMetadata(BaseModel):
    recipe_type: str = Field(alias="recipeType")
    disciplines: list[str] | None = None
    min_rating: int | None = Field(default=None, alias="minRating")


class VendorMetadata(BaseModel):
    map_id: int | None = Field(default=None, alias="mapId")
    limit_type: Literal["daily", "weekly", "season", "lifetime"] | None = Field(
        default=None, alias="limitType"
    )
    limit_amount: int | None = Field(default=None, alias="limitAmount")
    notes: str | None = None


class AchievementMetadata(BaseModel):
    achievement_id: int | None = Field(default=None, alias="achievementId")
    achievement_name: str = Field(alias="achievementName")
    achievement_category: str | None = Field(default=None, alias="achievementCategory")
    description: str | None = None
    wiki_url: str | None = Field(default=None, alias="wikiUrl")
    repeatable: bool = False
    time_gated: bool = Field(default=False, alias="timeGated")


class ContainerMetadata(BaseModel):
    container_item_id: int | None = Field(default=None, alias="containerItemId", gt=0)
    guaranteed: bool | None = None
    choice: bool | None = None


class SalvageMetadata(BaseModel):
    source_item_id: int | None = Field(default=None, alias="sourceItemId", gt=0)
    guaranteed: bool | None = None


class RewardTrackMetadata(BaseModel):
    track_name: str = Field(alias="trackName")
    track_type: Literal["wvw", "pvp"] = Field(alias="trackType")
    wiki_url: str | None = Field(default=None, alias="wikiUrl")


class MapRewardMetadata(BaseModel):
    reward_type: Literal["world_completion", "region_completion", "map_completion"] = Field(
        alias="rewardType"
    )
    region_name: str | None = Field(default=None, alias="regionName")
    estimated_hours: float | None = Field(default=None, alias="estimatedHours")
    notes: str | None = None


class WizardsVaultMetadata(BaseModel):
    seasonal: bool = False


class StoryMetadata(BaseModel):
    story_chapter: str | None = Field(default=None, alias="storyChapter")
    expansion: str | None = None


AcquisitionMetadata = (
    RecipeMetadata
    | VendorMetadata
    | AchievementMetadata
    | ContainerMetadata
    | SalvageMetadata
    | RewardTrackMetadata
    | MapRewardMetadata
    | WizardsVaultMetadata
    | StoryMetadata
)

_METADATA_BY_ACQUISITION_TYPE: dict[str, type[BaseModel]] = {
    "crafting": RecipeMetadata,
    "mystic_forge": RecipeMetadata,
    "vendor": VendorMetadata,
    "achievement": AchievementMetadata,
    "map_reward": MapRewardMetadata,
    "container": ContainerMetadata,
    "salvage": SalvageMetadata,
    "wvw_reward": RewardTrackMetadata,
    "pvp_reward": RewardTrackMetadata,
    "wizards_vault": WizardsVaultMetadata,
    "story": StoryMetadata,
}


# --- Acquisition ---


class Acquisition(BaseModel):
    type: AcquisitionType
    vendor_name: str | None = Field(default=None, alias="vendorName")
    discontinued: bool | None = None
    output_quantity: int = Field(default=1, ge=1, alias="outputQuantity")
    requirements: list[AcquisitionRequirement] = Field(default_factory=list)
    metadata: AcquisitionMetadata | dict | None = None

    model_config = {"populate_by_name": True}


# --- Item File ---


class ItemFile(BaseModel):
    id: int = Field(gt=0)
    name: str
    type: ItemType
    rarity: ItemRarity
    level: int = Field(ge=0)
    icon: str | None = None
    description: str | None = None
    vendor_value: int | None = Field(default=None, alias="vendorValue")
    flags: list[str] = Field(default_factory=list)
    wiki_url: str | None = Field(default=None, alias="wikiUrl")
    last_updated: str = Field(alias="lastUpdated")
    acquisitions: list[Acquisition] = Field(default_factory=list)

    model_config = {"populate_by_name": True}
