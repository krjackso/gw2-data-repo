"""Tests for the acquisition data schema and Pydantic models."""

import json
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator

from src.gw2_data.models import AcquisitionFile

SCHEMA_PATH = Path(__file__).parent.parent / "schema" / "acquisition.schema.json"


@pytest.fixture
def schema():
    with open(SCHEMA_PATH) as f:
        return json.load(f)


@pytest.fixture
def validator(schema):
    return Draft202012Validator(schema)


VALID_MINIMAL = """
itemId: 19721
itemName: Glob of Ectoplasm
lastUpdated: "2025-06-15"
acquisitions: []
"""

VALID_FULL = """
itemId: 19676
itemName: Gift of Metal
wikiUrl: https://wiki.guildwars2.com/wiki/Gift_of_Metal
lastUpdated: "2025-06-15"
acquisitions:
  - type: mystic_forge
    outputQuantity: 1
    requirements:
      - type: item
        itemId: 19684
        name: Orichalcum Ingot
        quantity: 250
      - type: item
        itemId: 19683
        name: Mithril Ingot
        quantity: 250
      - type: item
        itemId: 19688
        name: Darksteel Ingot
        quantity: 250
      - type: item
        itemId: 19682
        name: Platinum Ingot
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
    outputQuantity: 1
    requirements:
      - type: currency
        currencyId: 2
        name: Karma
        quantity: 2100
    metadata:
      vendorName: Miyani
      vendorLocation: Mystic Forge
"""

VALID_WITH_VENDOR_LIMIT = """
itemId: 19925
itemName: Obsidian Shard
lastUpdated: "2025-06-15"
acquisitions:
  - type: vendor
    outputQuantity: 1
    requirements:
      - type: currency
        currencyId: 2
        name: Karma
        quantity: 2100
    metadata:
      vendorName: Miyani
      vendorLocation: Mystic Forge
      limitType: daily
      limitAmount: 5
"""

VALID_WITH_MAP_REWARD = """
itemId: 19677
itemName: Gift of Exploration
lastUpdated: "2025-06-15"
acquisitions:
  - type: map_reward
    outputQuantity: 2
    requirements: []
    metadata:
      rewardType: world_completion
      regionName: Central Tyria
      estimatedHours:
        min: 20
        max: 30
      wikiUrl: https://wiki.guildwars2.com/wiki/Map_completion
      notes: Once per character
"""

VALID_WITH_CONTAINER = """
itemId: 105921
itemName: Selachimorpha (Light)
lastUpdated: "2025-06-15"
acquisitions:
  - type: container
    outputQuantity: 1
    requirements:
      - type: item
        itemId: 105743
        name: Selachimorpha Container
        quantity: 1
    metadata:
      containerItemId: 105743
      containerName: Selachimorpha Container
"""

VALID_WITH_UNRESOLVED = """
itemId: 99999
itemName: Unknown Item
lastUpdated: "2025-06-15"
acquisitions:
  - type: vendor
    outputQuantity: 1
    requirements:
      - type: unresolved
        name: Some Unknown Currency
        quantity: 50
    metadata:
      vendorName: Mystery Vendor
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

    def test_valid_with_unresolved(self, validator):
        data = yaml.safe_load(VALID_WITH_UNRESOLVED)
        errors = list(validator.iter_errors(data))
        assert errors == []

    def test_missing_required_fields(self, validator):
        data = {"itemId": 123}
        errors = list(validator.iter_errors(data))
        assert len(errors) > 0
        messages = [e.message for e in errors]
        assert any("itemName" in m for m in messages)
        assert any("lastUpdated" in m for m in messages)
        assert any("acquisitions" in m for m in messages)

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
                "requirements": [{"type": "item", "itemId": 1, "name": "Test", "quantity": -1}],
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
        result = AcquisitionFile.model_validate(data)
        assert result.item_id == 19721
        assert result.item_name == "Glob of Ectoplasm"
        assert result.acquisitions == []

    def test_parse_full(self):
        data = yaml.safe_load(VALID_FULL)
        result = AcquisitionFile.model_validate(data)
        assert result.item_id == 19676
        assert result.item_name == "Gift of Metal"
        assert len(result.acquisitions) == 3
        assert result.acquisitions[0].type == "mystic_forge"
        assert len(result.acquisitions[0].requirements) == 4
        assert result.acquisitions[1].type == "achievement"
        assert result.acquisitions[2].type == "vendor"

    def test_parse_item_requirement(self):
        data = yaml.safe_load(VALID_FULL)
        result = AcquisitionFile.model_validate(data)
        req = result.acquisitions[0].requirements[0]
        assert req.type == "item"
        assert req.item_id == 19684
        assert req.name == "Orichalcum Ingot"
        assert req.quantity == 250

    def test_parse_currency_requirement(self):
        data = yaml.safe_load(VALID_FULL)
        result = AcquisitionFile.model_validate(data)
        req = result.acquisitions[2].requirements[0]
        assert req.type == "currency"
        assert req.currency_id == 2
        assert req.name == "Karma"
        assert req.quantity == 2100

    def test_parse_unresolved_requirement(self):
        data = yaml.safe_load(VALID_WITH_UNRESOLVED)
        result = AcquisitionFile.model_validate(data)
        req = result.acquisitions[0].requirements[0]
        assert req.type == "unresolved"
        assert req.name == "Some Unknown Currency"
        assert req.quantity == 50

    def test_parse_map_reward(self):
        data = yaml.safe_load(VALID_WITH_MAP_REWARD)
        result = AcquisitionFile.model_validate(data)
        acq = result.acquisitions[0]
        assert acq.type == "map_reward"
        assert acq.output_quantity == 2

    def test_parse_container(self):
        data = yaml.safe_load(VALID_WITH_CONTAINER)
        result = AcquisitionFile.model_validate(data)
        acq = result.acquisitions[0]
        assert acq.type == "container"
        assert acq.requirements[0].item_id == 105743

    def test_missing_required_field_raises(self):
        data = {"itemId": 123}
        with pytest.raises(Exception):
            AcquisitionFile.model_validate(data)

    def test_all_acquisition_types_accepted(self):
        for acq_type in [
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
        ]:
            data = {
                "itemId": 1,
                "itemName": "Test",
                "lastUpdated": "2025-01-01",
                "acquisitions": [{"type": acq_type}],
            }
            result = AcquisitionFile.model_validate(data)
            assert result.acquisitions[0].type == acq_type
