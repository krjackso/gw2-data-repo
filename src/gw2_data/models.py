"""Pydantic models for GW2 item data with acquisition methods."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator

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
    "other",
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
    description: str | None = None
    wiki_url: str | None = Field(default=None, alias="wikiUrl")
    repeatable: bool = False
    time_gated: bool = Field(default=False, alias="timeGated")


class ContainerMetadata(BaseModel):
    guaranteed: bool | None = None
    choice: bool | None = None


class SalvageMetadata(BaseModel):
    guaranteed: bool | None = None


class RewardTrackMetadata(BaseModel):
    wiki_url: str | None = Field(default=None, alias="wikiUrl")


class MapRewardMetadata(BaseModel):
    reward_type: Literal["world_completion", "region_completion", "map_completion"] = Field(
        alias="rewardType"
    )
    region_name: str | None = Field(default=None, alias="regionName")
    estimated_hours: float | None = Field(default=None, alias="estimatedHours")
    notes: str | None = None


class WizardsVaultMetadata(BaseModel):
    limit_amount: int | None = Field(default=None, alias="limitAmount")


class StoryMetadata(BaseModel):
    story_chapter: str | None = Field(default=None, alias="storyChapter")
    expansion: str | None = None


class OtherMetadata(BaseModel):
    notes: str


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
    | OtherMetadata
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
    "other": OtherMetadata,
}


# --- Acquisition ---


class Acquisition(BaseModel):
    type: AcquisitionType
    vendor_name: str | None = Field(default=None, alias="vendorName")
    achievement_name: str | None = Field(default=None, alias="achievementName")
    achievement_category: str | None = Field(default=None, alias="achievementCategory")
    track_name: str | None = Field(default=None, alias="trackName")
    item_id: int | None = Field(default=None, alias="itemId", gt=0)
    output_quantity: int = Field(default=1, ge=1, alias="outputQuantity")
    output_quantity_min: int | None = Field(default=None, ge=1, alias="outputQuantityMin")
    output_quantity_max: int | None = Field(default=None, ge=1, alias="outputQuantityMax")
    requirements: list[AcquisitionRequirement] = Field(default_factory=list)
    metadata: AcquisitionMetadata | dict | None = None

    model_config = {"populate_by_name": True}

    @model_validator(mode="after")
    def _validate_output_quantity_range(self) -> Acquisition:
        if self.output_quantity_max is not None and self.output_quantity_min is None:
            raise ValueError("outputQuantityMin is required when outputQuantityMax is present")
        if (
            self.output_quantity_min is not None
            and self.output_quantity != self.output_quantity_min
        ):
            raise ValueError(
                f"outputQuantity ({self.output_quantity}) must equal "
                f"outputQuantityMin ({self.output_quantity_min}) when range is specified"
            )
        if (
            self.output_quantity_min is not None
            and self.output_quantity_max is not None
            and self.output_quantity_max < self.output_quantity_min
        ):
            raise ValueError(
                f"outputQuantityMax ({self.output_quantity_max}) must be >= "
                f"outputQuantityMin ({self.output_quantity_min})"
            )
        return self


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
