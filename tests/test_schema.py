"""Tests for the item data schema and Pydantic models."""

import json
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator

from src.gw2_data.models import ItemFile

SCHEMA_PATH = Path(__file__).parent.parent / "data" / "schema" / "item.schema.json"


@pytest.fixture
def schema():
    with open(SCHEMA_PATH) as f:
        return json.load(f)


@pytest.fixture
def validator(schema):
    return Draft202012Validator(schema)


VALID_MINIMAL = """
id: 19721
name: Glob of Ectoplasm
type: CraftingMaterial
rarity: Rare
level: 0
lastUpdated: "2025-06-15"
acquisitions: []
"""

VALID_FULL = """
id: 19676
name: Gift of Metal
type: Trophy
rarity: Legendary
level: 0
icon: https://render.guildwars2.com/file/ABC123.png
description: A gift for the Mystic Forge
vendorValue: 0
flags:
  - AccountBound
  - NoSell
wikiUrl: https://wiki.guildwars2.com/wiki/Gift_of_Metal
lastUpdated: "2025-06-15"
acquisitions:
  - type: mystic_forge
    outputQuantity: 1
    requirements:
      - itemId: 19684
        quantity: 250
      - itemId: 19683
        quantity: 250
      - itemId: 19688
        quantity: 250
      - itemId: 19682
        quantity: 250
    metadata:
      recipeType: mystic_forge
  - type: achievement
    outputQuantity: 1
    requirements: []
    metadata:
      achievementName: Lessons in Metallurgy
      achievementCategory: Collections
      repeatable: false
      timeGated: false
  - type: vendor
    vendorName: Miyani
    outputQuantity: 1
    requirements:
      - currencyId: 2
        quantity: 2100
"""

VALID_WITH_VENDOR_LIMIT = """
id: 19925
name: Obsidian Shard
type: CraftingMaterial
rarity: Exotic
level: 0
lastUpdated: "2025-06-15"
acquisitions:
  - type: vendor
    vendorName: Miyani
    outputQuantity: 1
    requirements:
      - currencyId: 2
        quantity: 2100
    metadata:
      limitType: daily
      limitAmount: 5
"""

VALID_WITH_MAP_REWARD = """
id: 19677
name: Gift of Exploration
type: Trophy
rarity: Legendary
level: 0
lastUpdated: "2025-06-15"
acquisitions:
  - type: map_reward
    outputQuantity: 2
    requirements: []
    metadata:
      rewardType: world_completion
      regionName: Central Tyria
      estimatedHours: 25.5
      notes: Once per character
"""

VALID_WITH_CONTAINER = """
id: 105921
name: Selachimorpha (Light)
type: Armor
rarity: Ascended
level: 80
lastUpdated: "2025-06-15"
acquisitions:
  - type: container
    outputQuantity: 1
    requirements:
      - itemId: 105743
        quantity: 1
    metadata:
      containerItemId: 105743
"""


class TestJsonSchema:
    def test_valid_minimal(self, validator):
        data = yaml.safe_load(VALID_MINIMAL)
        errors = list(validator.iter_errors(data))
        assert errors == []

    def test_valid_full(self, validator):
        data = yaml.safe_load(VALID_FULL)
        errors = list(validator.iter_errors(data))
        assert errors == []

    def test_valid_with_map_reward(self, validator):
        data = yaml.safe_load(VALID_WITH_MAP_REWARD)
        errors = list(validator.iter_errors(data))
        assert errors == []

    def test_valid_with_container(self, validator):
        data = yaml.safe_load(VALID_WITH_CONTAINER)
        errors = list(validator.iter_errors(data))
        assert errors == []

    def test_missing_required_fields(self, validator):
        data = {"id": 123}
        errors = list(validator.iter_errors(data))
        assert len(errors) > 0
        messages = [e.message for e in errors]
        assert any("name" in m for m in messages)
        assert any("type" in m for m in messages)
        assert any("rarity" in m for m in messages)
        assert any("level" in m for m in messages)
        assert any("lastUpdated" in m for m in messages)

    def test_invalid_acquisition_type(self, validator):
        data = yaml.safe_load(VALID_MINIMAL)
        data["acquisitions"] = [{"type": "invalid_type"}]
        errors = list(validator.iter_errors(data))
        assert len(errors) > 0

    def test_negative_quantity(self, validator):
        data = yaml.safe_load(VALID_MINIMAL)
        data["acquisitions"] = [
            {
                "type": "vendor",
                "requirements": [{"itemId": 1, "quantity": -1}],
            }
        ]
        errors = list(validator.iter_errors(data))
        assert len(errors) > 0

    def test_no_extra_properties_on_root(self, validator):
        data = yaml.safe_load(VALID_MINIMAL)
        data["extraField"] = "not allowed"
        errors = list(validator.iter_errors(data))
        assert len(errors) > 0


class TestPydanticModels:
    def test_parse_minimal(self):
        data = yaml.safe_load(VALID_MINIMAL)
        result = ItemFile.model_validate(data)
        assert result.id == 19721
        assert result.name == "Glob of Ectoplasm"
        assert result.type == "CraftingMaterial"
        assert result.rarity == "Rare"
        assert result.level == 0
        assert result.acquisitions == []

    def test_parse_full(self):
        data = yaml.safe_load(VALID_FULL)
        result = ItemFile.model_validate(data)
        assert result.id == 19676
        assert result.name == "Gift of Metal"
        assert result.type == "Trophy"
        assert result.rarity == "Legendary"
        assert result.icon == "https://render.guildwars2.com/file/ABC123.png"
        assert "AccountBound" in result.flags
        assert "NoSell" in result.flags
        assert len(result.acquisitions) == 3
        assert result.acquisitions[0].type == "mystic_forge"
        assert len(result.acquisitions[0].requirements) == 4
        assert result.acquisitions[1].type == "achievement"
        assert result.acquisitions[2].type == "vendor"

    def test_parse_item_requirement(self):
        data = yaml.safe_load(VALID_FULL)
        result = ItemFile.model_validate(data)
        req = result.acquisitions[0].requirements[0]
        assert req.item_id == 19684
        assert req.quantity == 250

    def test_parse_currency_requirement(self):
        data = yaml.safe_load(VALID_FULL)
        result = ItemFile.model_validate(data)
        req = result.acquisitions[2].requirements[0]
        assert req.currency_id == 2
        assert req.quantity == 2100

    def test_parse_map_reward(self):
        data = yaml.safe_load(VALID_WITH_MAP_REWARD)
        result = ItemFile.model_validate(data)
        acq = result.acquisitions[0]
        assert acq.type == "map_reward"
        assert acq.output_quantity == 2

    def test_parse_container(self):
        data = yaml.safe_load(VALID_WITH_CONTAINER)
        result = ItemFile.model_validate(data)
        acq = result.acquisitions[0]
        assert acq.type == "container"
        assert acq.requirements[0].item_id == 105743

    def test_missing_required_field_raises(self):
        data = {"id": 123}
        with pytest.raises(Exception):
            ItemFile.model_validate(data)

    def test_all_acquisition_types_accepted(self):
        for acq_type in [
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
        ]:
            data = {
                "id": 1,
                "name": "Test",
                "type": "Trophy",
                "rarity": "Legendary",
                "level": 0,
                "lastUpdated": "2025-01-01",
                "acquisitions": [{"type": acq_type}],
            }
            result = ItemFile.model_validate(data)
            assert result.acquisitions[0].type == acq_type
