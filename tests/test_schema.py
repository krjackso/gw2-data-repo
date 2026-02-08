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
    achievementName: Lessons in Metallurgy
    achievementCategory: Collections
    outputQuantity: 1
    requirements: []
    metadata:
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
    containerName: Chest of Legendary Armor
    itemId: 105743
    outputQuantity: 1
    requirements: []
    metadata:
      guaranteed: false
"""

VALID_WITH_CONTAINER_NAME_ONLY = """
id: 90783
name: Mistborn Mote
type: CraftingMaterial
rarity: Rare
level: 0
lastUpdated: "2025-06-15"
acquisitions:
  - type: container
    containerName: Mistborn Coffer
    outputQuantity: 1
    requirements: []
    metadata:
      guaranteed: true
"""

VALID_WITH_CONTAINER_BOTH = """
id: 67219
name: Test Item
type: CraftingMaterial
rarity: Exotic
level: 0
lastUpdated: "2025-06-15"
acquisitions:
  - type: container
    containerName: Some Container
    itemId: 12345
    outputQuantity: 1
    requirements: []
    metadata:
      guaranteed: true
"""

INVALID_CONTAINER_MISSING_NAME = """
id: 90783
name: Test Item
type: CraftingMaterial
rarity: Rare
level: 0
lastUpdated: "2025-06-15"
acquisitions:
  - type: container
    outputQuantity: 1
    requirements: []
    metadata:
      guaranteed: true
"""

VALID_WITH_OUTPUT_RANGE = """
id: 24276
name: Pile of Incandescent Dust
type: CraftingMaterial
rarity: Fine
level: 0
lastUpdated: "2025-06-15"
acquisitions:
  - type: mystic_forge
    outputQuantity: 40
    outputQuantityMin: 40
    outputQuantityMax: 200
    requirements:
      - itemId: 20796
        quantity: 4
      - itemId: 20799
        quantity: 4
      - itemId: 24562
        quantity: 250
      - itemId: 24276
        quantity: 1
    metadata:
      recipeType: mystic_forge
"""

INVALID_OUTPUT_RANGE_MAX_LT_MIN = """
id: 24276
name: Test Item
type: CraftingMaterial
rarity: Fine
level: 0
lastUpdated: "2025-06-15"
acquisitions:
  - type: mystic_forge
    outputQuantity: 200
    outputQuantityMin: 200
    outputQuantityMax: 40
    requirements: []
    metadata:
      recipeType: mystic_forge
"""

INVALID_OUTPUT_RANGE_MAX_WITHOUT_MIN = """
id: 24276
name: Test Item
type: CraftingMaterial
rarity: Fine
level: 0
lastUpdated: "2025-06-15"
acquisitions:
  - type: mystic_forge
    outputQuantity: 40
    outputQuantityMax: 200
    requirements: []
    metadata:
      recipeType: mystic_forge
"""

VALID_WITH_RESOURCE_NODE = """
id: 90783
name: Mistborn Mote
type: CraftingMaterial
rarity: Rare
level: 0
lastUpdated: "2025-06-15"
acquisitions:
  - type: resource_node
    nodeName: Mistborn Mote node
    outputQuantity: 1
    outputQuantityMin: 1
    outputQuantityMax: 3
    requirements: []
    metadata:
      guaranteed: true
"""

INVALID_RESOURCE_NODE_MISSING_NAME = """
id: 90783
name: Test Item
type: CraftingMaterial
rarity: Rare
level: 0
lastUpdated: "2025-06-15"
acquisitions:
  - type: resource_node
    outputQuantity: 1
    requirements: []
    metadata:
      guaranteed: true
"""

INVALID_OUTPUT_RANGE_QUANTITY_NE_MIN = """
id: 24276
name: Test Item
type: CraftingMaterial
rarity: Fine
level: 0
lastUpdated: "2025-06-15"
acquisitions:
  - type: mystic_forge
    outputQuantity: 50
    outputQuantityMin: 40
    outputQuantityMax: 200
    requirements: []
    metadata:
      recipeType: mystic_forge
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

    def test_valid_with_container_name_only(self, validator):
        data = yaml.safe_load(VALID_WITH_CONTAINER_NAME_ONLY)
        errors = list(validator.iter_errors(data))
        assert errors == []

    def test_valid_with_container_both(self, validator):
        data = yaml.safe_load(VALID_WITH_CONTAINER_BOTH)
        errors = list(validator.iter_errors(data))
        assert errors == []

    def test_valid_with_resource_node(self, validator):
        data = yaml.safe_load(VALID_WITH_RESOURCE_NODE)
        errors = list(validator.iter_errors(data))
        assert errors == []

    def test_valid_with_output_range(self, validator):
        data = yaml.safe_load(VALID_WITH_OUTPUT_RANGE)
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
        assert acq.container_name == "Chest of Legendary Armor"
        assert acq.item_id == 105743
        assert acq.requirements == []

    def test_parse_container_name_only(self):
        data = yaml.safe_load(VALID_WITH_CONTAINER_NAME_ONLY)
        result = ItemFile.model_validate(data)
        acq = result.acquisitions[0]
        assert acq.type == "container"
        assert acq.container_name == "Mistborn Coffer"
        assert acq.item_id is None

    def test_parse_container_both_name_and_id(self):
        data = yaml.safe_load(VALID_WITH_CONTAINER_BOTH)
        result = ItemFile.model_validate(data)
        acq = result.acquisitions[0]
        assert acq.type == "container"
        assert acq.container_name == "Some Container"
        assert acq.item_id == 12345

    def test_container_missing_name_raises(self):
        data = yaml.safe_load(INVALID_CONTAINER_MISSING_NAME)
        with pytest.raises(Exception, match="containerName is required"):
            ItemFile.model_validate(data)

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
            "resource_node",
            "wvw_reward",
            "pvp_reward",
            "wizards_vault",
            "other",
        ]:
            acq: dict = {"type": acq_type}
            if acq_type == "container":
                acq["containerName"] = "Test Container"
            if acq_type == "resource_node":
                acq["nodeName"] = "Test Node"
            data = {
                "id": 1,
                "name": "Test",
                "type": "Trophy",
                "rarity": "Legendary",
                "level": 0,
                "lastUpdated": "2025-01-01",
                "acquisitions": [acq],
            }
            result = ItemFile.model_validate(data)
            assert result.acquisitions[0].type == acq_type

    def test_parse_resource_node(self):
        data = yaml.safe_load(VALID_WITH_RESOURCE_NODE)
        result = ItemFile.model_validate(data)
        acq = result.acquisitions[0]
        assert acq.type == "resource_node"
        assert acq.node_name == "Mistborn Mote node"
        assert acq.output_quantity == 1
        assert acq.output_quantity_min == 1
        assert acq.output_quantity_max == 3

    def test_resource_node_missing_name_raises(self):
        data = yaml.safe_load(INVALID_RESOURCE_NODE_MISSING_NAME)
        with pytest.raises(Exception, match="nodeName is required"):
            ItemFile.model_validate(data)

    def test_valid_output_range(self):
        data = yaml.safe_load(VALID_WITH_OUTPUT_RANGE)
        result = ItemFile.model_validate(data)
        acq = result.acquisitions[0]
        assert acq.output_quantity == 40
        assert acq.output_quantity_min == 40
        assert acq.output_quantity_max == 200

    def test_invalid_output_range_max_lt_min(self):
        data = yaml.safe_load(INVALID_OUTPUT_RANGE_MAX_LT_MIN)
        with pytest.raises(Exception, match="outputQuantityMax.*must be >=.*outputQuantityMin"):
            ItemFile.model_validate(data)

    def test_invalid_output_range_max_without_min(self):
        data = yaml.safe_load(INVALID_OUTPUT_RANGE_MAX_WITHOUT_MIN)
        with pytest.raises(Exception, match="outputQuantityMin is required when outputQuantityMax"):
            ItemFile.model_validate(data)

    def test_invalid_output_range_quantity_ne_min(self):
        data = yaml.safe_load(INVALID_OUTPUT_RANGE_QUANTITY_NE_MIN)
        with pytest.raises(Exception, match="outputQuantity.*must equal.*outputQuantityMin"):
            ItemFile.model_validate(data)
