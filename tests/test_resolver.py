import pytest

from gw2_data import resolver
from gw2_data.exceptions import APIError


def test_resolve_requirements_with_item_names():
    item_index = {"Sword": [123], "Shield": [456]}
    currency_index = {"Coin": 1}
    acquisitions = [
        {
            "type": "crafting",
            "requirements": [
                {"itemName": "Sword", "quantity": 1},
                {"itemName": "Shield", "quantity": 2},
            ],
        }
    ]

    result = resolver.resolve_requirements(acquisitions, item_index, currency_index)

    assert len(result) == 1
    assert result[0]["type"] == "crafting"
    assert len(result[0]["requirements"]) == 2
    assert result[0]["requirements"][0] == {"itemId": 123, "quantity": 1}
    assert result[0]["requirements"][1] == {"itemId": 456, "quantity": 2}


def test_resolve_requirements_with_currency_names():
    item_index = {}
    currency_index = {"Coin": 1, "Karma": 2}
    acquisitions = [
        {
            "type": "vendor",
            "requirements": [
                {"currencyName": "Coin", "quantity": 10000},
                {"currencyName": "Karma", "quantity": 5000},
            ],
        }
    ]

    result = resolver.resolve_requirements(acquisitions, item_index, currency_index)

    assert len(result) == 1
    assert result[0]["type"] == "vendor"
    assert len(result[0]["requirements"]) == 2
    assert result[0]["requirements"][0] == {"currencyId": 1, "quantity": 10000}
    assert result[0]["requirements"][1] == {"currencyId": 2, "quantity": 5000}


def test_resolve_requirements_with_mixed_names():
    item_index = {"Orichalcum Ingot": [19685]}
    currency_index = {"Coin": 1}
    acquisitions = [
        {
            "type": "vendor",
            "requirements": [
                {"itemName": "Orichalcum Ingot", "quantity": 250},
                {"currencyName": "Coin", "quantity": 50000},
            ],
        }
    ]

    result = resolver.resolve_requirements(acquisitions, item_index, currency_index)

    assert len(result) == 1
    assert len(result[0]["requirements"]) == 2
    assert result[0]["requirements"][0] == {"itemId": 19685, "quantity": 250}
    assert result[0]["requirements"][1] == {"currencyId": 1, "quantity": 50000}


def test_resolve_requirements_empty_list():
    item_index = {}
    currency_index = {}
    acquisitions = []

    result = resolver.resolve_requirements(acquisitions, item_index, currency_index)

    assert result == []


def test_resolve_requirements_no_requirements():
    item_index = {}
    currency_index = {}
    acquisitions = [{"type": "achievement", "requirements": []}]

    result = resolver.resolve_requirements(acquisitions, item_index, currency_index)

    assert len(result) == 1
    assert result[0]["requirements"] == []


def test_resolve_requirements_item_not_found():
    item_index = {"Sword": [123]}
    currency_index = {}
    acquisitions = [
        {
            "type": "crafting",
            "requirements": [{"itemName": "NonexistentItem", "quantity": 1}],
        }
    ]

    with pytest.raises(ValueError, match="Failed to resolve item 'NonexistentItem'"):
        resolver.resolve_requirements(acquisitions, item_index, currency_index)


def test_resolve_requirements_currency_not_found():
    item_index = {}
    currency_index = {"Coin": 1}
    acquisitions = [
        {
            "type": "vendor",
            "requirements": [{"currencyName": "InvalidCurrency", "quantity": 100}],
        }
    ]

    with pytest.raises(ValueError, match="Failed to resolve currency 'InvalidCurrency'"):
        resolver.resolve_requirements(acquisitions, item_index, currency_index)


def test_resolve_requirements_item_duplicate_names():
    item_index = {"Sword": [123, 456]}
    currency_index = {}
    acquisitions = [{"type": "crafting", "requirements": [{"itemName": "Sword", "quantity": 1}]}]

    with pytest.raises(ValueError, match="Failed to resolve item 'Sword'"):
        with pytest.raises(APIError, match="matches multiple IDs"):
            resolver.resolve_requirements(acquisitions, item_index, currency_index)


def test_resolve_requirements_preserves_existing_ids():
    item_index = {"Sword": [123]}
    currency_index = {"Coin": 1}
    acquisitions = [
        {
            "type": "vendor",
            "requirements": [
                {"itemId": 999, "quantity": 1},
                {"currencyId": 2, "quantity": 100},
            ],
        }
    ]

    result = resolver.resolve_requirements(acquisitions, item_index, currency_index)

    assert result[0]["requirements"][0] == {"itemId": 999, "quantity": 1}
    assert result[0]["requirements"][1] == {"currencyId": 2, "quantity": 100}


def test_resolve_requirements_preserves_other_fields():
    item_index = {"Sword": [123]}
    currency_index = {}
    acquisitions = [
        {
            "type": "crafting",
            "outputQuantity": 5,
            "metadata": {"recipeType": "crafting"},
            "requirements": [{"itemName": "Sword", "quantity": 1}],
        }
    ]

    result = resolver.resolve_requirements(acquisitions, item_index, currency_index)

    assert result[0]["type"] == "crafting"
    assert result[0]["outputQuantity"] == 5
    assert result[0]["metadata"] == {"recipeType": "crafting"}
    assert result[0]["requirements"] == [{"itemId": 123, "quantity": 1}]


def test_resolve_requirements_multiple_acquisitions():
    item_index = {"Sword": [123], "Shield": [456]}
    currency_index = {"Coin": 1}
    acquisitions = [
        {"type": "crafting", "requirements": [{"itemName": "Sword", "quantity": 1}]},
        {"type": "vendor", "requirements": [{"currencyName": "Coin", "quantity": 100}]},
        {"type": "achievement", "requirements": []},
    ]

    result = resolver.resolve_requirements(acquisitions, item_index, currency_index)

    assert len(result) == 3
    assert result[0]["requirements"][0] == {"itemId": 123, "quantity": 1}
    assert result[1]["requirements"][0] == {"currencyId": 1, "quantity": 100}
    assert result[2]["requirements"] == []


def test_resolve_requirements_error_includes_acquisition_type():
    item_index = {}
    currency_index = {}
    acquisitions = [
        {"type": "mystic_forge", "requirements": [{"itemName": "Missing", "quantity": 1}]}
    ]

    with pytest.raises(ValueError, match="in mystic_forge acquisition"):
        resolver.resolve_requirements(acquisitions, item_index, currency_index)


def test_resolve_requirements_with_name_overrides():
    item_index = {
        "Agaleus": [105438, 105738, 106400],
        "Agaleus (heavy)": [105738],
        "Agaleus (medium)": [106400],
        "Agaleus (light)": [105438],
        "Gift of Metal": [19676],
    }
    currency_index = {}
    acquisitions = [
        {
            "type": "mystic_forge",
            "outputQuantity": 1,
            "requirements": [
                {"itemName": "Agaleus (heavy)", "quantity": 1},
                {"itemName": "Gift of Metal", "quantity": 1},
            ],
            "metadata": {"recipeType": "mystic_forge"},
        }
    ]

    result = resolver.resolve_requirements(acquisitions, item_index, currency_index)

    assert len(result) == 1
    assert result[0]["requirements"][0]["itemId"] == 105738
    assert result[0]["requirements"][1]["itemId"] == 19676
    assert "itemName" not in result[0]["requirements"][0]
    assert "itemName" not in result[0]["requirements"][1]
