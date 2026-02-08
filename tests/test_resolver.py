import pytest

from gw2_data import resolver


def test_resolve_requirements_empty_list():
    item_index = {}
    currency_index = {}

    result = resolver.resolve_requirements([], item_index, currency_index)

    assert result == []


def test_resolve_requirements_no_requirements():
    item_index = {}
    currency_index = {}
    acquisitions = [{"type": "achievement", "requirements": []}]

    result = resolver.resolve_requirements(acquisitions, item_index, currency_index)

    assert len(result) == 1
    assert result[0]["requirements"] == []


def test_resolve_requirements_preserves_existing_ids():
    item_index = {}
    currency_index = {}
    acquisitions = [
        {
            "type": "crafting",
            "requirements": [
                {"itemId": 999, "quantity": 5},
                {"currencyId": 1, "quantity": 100},
            ],
        }
    ]

    result = resolver.resolve_requirements(acquisitions, item_index, currency_index)

    assert len(result) == 1
    assert result[0]["requirements"][0] == {"itemId": 999, "quantity": 5}
    assert result[0]["requirements"][1] == {"currencyId": 1, "quantity": 100}


def test_resolve_requirements_preserves_other_fields():
    item_index = {}
    currency_index = {}
    acquisitions = [
        {
            "type": "vendor",
            "vendorName": "Test Vendor",
            "outputQuantity": 1,
            "requirements": [],
            "metadata": {"limitType": "daily"},
        }
    ]

    result = resolver.resolve_requirements(acquisitions, item_index, currency_index)

    assert len(result) == 1
    assert result[0]["type"] == "vendor"
    assert result[0]["vendorName"] == "Test Vendor"
    assert result[0]["outputQuantity"] == 1
    assert result[0]["metadata"] == {"limitType": "daily"}


def test_resolve_requirements_multiple_acquisitions():
    item_index = {"Item A": [111]}
    currency_index = {"Currency B": 222}
    acquisitions = [
        {"type": "crafting", "requirements": [{"requirementName": "Item A", "quantity": 1}]},
        {"type": "vendor", "requirements": [{"requirementName": "Currency B", "quantity": 100}]},
    ]

    result = resolver.resolve_requirements(acquisitions, item_index, currency_index)

    assert len(result) == 2
    assert result[0]["requirements"][0]["itemId"] == 111
    assert result[1]["requirements"][0]["currencyId"] == 222


def test_resolve_requirement_name_currency_first():
    item_index = {"Shard of Glory": [70820]}
    currency_index = {"Ascended Shards of Glory": 33, "Coin": 1}

    acquisitions = [
        {
            "type": "vendor",
            "vendorName": "Test Vendor",
            "outputQuantity": 1,
            "requirements": [
                {"requirementName": "Ascended Shards of Glory", "quantity": 100},
                {"requirementName": "Coin", "quantity": 20000},
            ],
            "metadata": {},
        }
    ]

    result = resolver.resolve_requirements(acquisitions, item_index, currency_index)

    assert len(result) == 1
    assert len(result[0]["requirements"]) == 2
    assert result[0]["requirements"][0]["currencyId"] == 33
    assert result[0]["requirements"][1]["currencyId"] == 1
    assert "requirementName" not in result[0]["requirements"][0]


def test_resolve_requirement_name_item_fallback():
    item_index = {"Grandmaster Mark": [456], "Shard of Glory": [70820]}
    currency_index = {"Coin": 1}

    acquisitions = [
        {
            "type": "vendor",
            "vendorName": "Test Vendor",
            "outputQuantity": 1,
            "requirements": [
                {"requirementName": "Grandmaster Mark", "quantity": 5},
                {"requirementName": "Shard of Glory", "quantity": 250},
            ],
            "metadata": {},
        }
    ]

    result = resolver.resolve_requirements(acquisitions, item_index, currency_index)

    assert len(result) == 1
    assert len(result[0]["requirements"]) == 2
    assert result[0]["requirements"][0]["itemId"] == 456
    assert result[0]["requirements"][1]["itemId"] == 70820
    assert "requirementName" not in result[0]["requirements"][0]


def test_resolve_requirement_name_mixed():
    item_index = {"Grandmaster Mark": [456]}
    currency_index = {"Ascended Shards of Glory": 33, "Coin": 1}

    acquisitions = [
        {
            "type": "vendor",
            "vendorName": "League Vendor",
            "outputQuantity": 1,
            "requirements": [
                {"requirementName": "Grandmaster Mark", "quantity": 5},
                {"requirementName": "Ascended Shards of Glory", "quantity": 350},
                {"requirementName": "Coin", "quantity": 20000},
            ],
            "metadata": {},
        }
    ]

    result = resolver.resolve_requirements(acquisitions, item_index, currency_index)

    assert len(result) == 1
    assert len(result[0]["requirements"]) == 3
    assert result[0]["requirements"][0]["itemId"] == 456
    assert result[0]["requirements"][1]["currencyId"] == 33
    assert result[0]["requirements"][2]["currencyId"] == 1


def test_resolve_requirement_name_not_found():
    item_index = {}
    currency_index = {}

    acquisitions = [
        {
            "type": "vendor",
            "vendorName": "Test Vendor",
            "outputQuantity": 1,
            "requirements": [{"requirementName": "Unknown Item", "quantity": 1}],
            "metadata": {},
        }
    ]

    with pytest.raises(ValueError, match="Failed to resolve requirement 'Unknown Item'"):
        resolver.resolve_requirements(acquisitions, item_index, currency_index)


def test_resolve_requirement_name_with_override():
    item_index = {"Ardent Glorious Armguards": [67131]}
    currency_index = {"Ascended Shards of Glory": 33}

    acquisitions = [
        {
            "type": "mystic_forge",
            "outputQuantity": 1,
            "requirements": [
                {"requirementName": "Ardent Glorious Armguards", "quantity": 1},
                {"requirementName": "Gift Item", "quantity": 1},
            ],
            "metadata": {"recipeType": "mystic_forge"},
        }
    ]

    item_index["Gift Item"] = [82350]
    result = resolver.resolve_requirements(acquisitions, item_index, currency_index)

    assert len(result) == 1
    assert result[0]["requirements"][0]["itemId"] == 67131
    assert result[0]["requirements"][1]["itemId"] == 82350
    assert "requirementName" not in result[0]["requirements"][0]


def test_resolve_requirement_error_message_includes_hint():
    item_index = {}
    currency_index = {}

    acquisitions = [
        {
            "type": "vendor",
            "vendorName": "Test Vendor",
            "outputQuantity": 1,
            "requirements": [{"requirementName": "Ambiguous Item", "quantity": 1}],
            "metadata": {},
        }
    ]

    with pytest.raises(
        ValueError, match="currency_name_overrides.yaml or item_name_overrides.yaml"
    ):
        resolver.resolve_requirements(acquisitions, item_index, currency_index)


def test_filter_discontinued_acquisitions():
    item_index = {"Valid Item": [123]}
    currency_index = {}

    acquisitions = [
        {
            "type": "vendor",
            "requirements": [{"requirementName": "Valid Item", "quantity": 1}],
        },
        {
            "type": "container",
            "discontinued": True,
            "requirements": [
                {"requirementName": "Tournament of Glory: Fourth Place", "quantity": 1}
            ],
        },
        {
            "type": "crafting",
            "requirements": [{"requirementName": "Valid Item", "quantity": 2}],
        },
    ]

    result = resolver.resolve_requirements(acquisitions, item_index, currency_index)

    assert len(result) == 2
    assert result[0]["type"] == "vendor"
    assert result[0]["requirements"][0]["itemId"] == 123
    assert result[1]["type"] == "crafting"
    assert result[1]["requirements"][0]["itemId"] == 123


def test_discontinued_acquisition_not_raise_error_for_unresolvable():
    item_index = {}
    currency_index = {}

    acquisitions = [
        {
            "type": "container",
            "discontinued": True,
            "requirements": [{"requirementName": "Removed Item From API", "quantity": 1}],
        }
    ]

    result = resolver.resolve_requirements(acquisitions, item_index, currency_index)

    assert len(result) == 0


def test_lenient_mode_skips_unresolvable():
    item_index = {"Valid Item": [123]}
    currency_index = {}

    acquisitions = [
        {
            "type": "vendor",
            "requirements": [{"requirementName": "Valid Item", "quantity": 1}],
        },
        {
            "type": "pvp_reward",
            "requirements": [{"requirementName": "Amnytas Gear Box", "quantity": 1}],
        },
        {
            "type": "crafting",
            "requirements": [{"requirementName": "Valid Item", "quantity": 2}],
        },
    ]

    item_index["Amnytas Gear Box"] = [100372, 100500]

    result = resolver.resolve_requirements(acquisitions, item_index, currency_index, strict=False)

    assert len(result) == 2
    assert result[0]["type"] == "vendor"
    assert result[1]["type"] == "crafting"


class TestIsChanceDrop:
    def test_container_guaranteed(self):
        acq = {"type": "container", "metadata": {"guaranteed": True, "choice": False}}
        assert not resolver._is_chance_drop(acq)

    def test_container_choice(self):
        acq = {"type": "container", "metadata": {"guaranteed": False, "choice": True}}
        assert not resolver._is_chance_drop(acq)

    def test_container_chance(self):
        acq = {"type": "container", "metadata": {"guaranteed": False, "choice": False}}
        assert resolver._is_chance_drop(acq)

    def test_container_no_metadata(self):
        acq = {"type": "container", "metadata": {}}
        assert resolver._is_chance_drop(acq)

    def test_container_missing_metadata(self):
        acq = {"type": "container"}
        assert resolver._is_chance_drop(acq)

    def test_salvage_guaranteed(self):
        acq = {"type": "salvage", "metadata": {"guaranteed": True}}
        assert not resolver._is_chance_drop(acq)

    def test_salvage_chance(self):
        acq = {"type": "salvage", "metadata": {"guaranteed": False}}
        assert resolver._is_chance_drop(acq)

    def test_salvage_no_metadata(self):
        acq = {"type": "salvage", "metadata": {}}
        assert resolver._is_chance_drop(acq)

    def test_salvage_missing_metadata(self):
        acq = {"type": "salvage"}
        assert resolver._is_chance_drop(acq)

    def test_other_types_not_affected(self):
        for acq_type in ("crafting", "mystic_forge", "vendor", "achievement", "other"):
            acq = {"type": acq_type, "metadata": {}}
            assert not resolver._is_chance_drop(acq)


class TestChanceDropFiltering:
    def test_filter_chance_containers(self):
        item_index = {"Guaranteed Box": [100], "Choice Box": [200], "Valid Item": [300]}
        currency_index = {}

        acquisitions = [
            {
                "type": "container",
                "requirementName": "Guaranteed Box",
                "requirements": [],
                "metadata": {"guaranteed": True, "choice": False},
            },
            {
                "type": "container",
                "requirementName": "Choice Box",
                "requirements": [],
                "metadata": {"guaranteed": False, "choice": True},
            },
            {
                "type": "container",
                "requirementName": "Random Drop Box",
                "requirements": [],
                "metadata": {"guaranteed": False, "choice": False},
            },
            {
                "type": "crafting",
                "requirements": [{"requirementName": "Valid Item", "quantity": 1}],
            },
        ]

        result = resolver.resolve_requirements(acquisitions, item_index, currency_index)

        assert len(result) == 3
        assert result[0]["type"] == "container"
        assert result[0]["itemId"] == 100
        assert result[1]["type"] == "container"
        assert result[1]["itemId"] == 200
        assert result[2]["type"] == "crafting"

    def test_filter_chance_containers_no_metadata(self):
        item_index = {}
        currency_index = {}

        acquisitions = [
            {
                "type": "container",
                "requirementName": "Some Box",
                "requirements": [],
                "metadata": {},
            },
        ]

        result = resolver.resolve_requirements(acquisitions, item_index, currency_index)

        assert len(result) == 0

    def test_filter_chance_salvage(self):
        item_index = {"Guaranteed Source": [400]}
        currency_index = {}

        acquisitions = [
            {
                "type": "salvage",
                "requirementName": "Guaranteed Source",
                "requirements": [],
                "metadata": {"guaranteed": True},
            },
            {
                "type": "salvage",
                "requirementName": "Chance Source",
                "requirements": [],
                "metadata": {"guaranteed": False},
            },
        ]

        result = resolver.resolve_requirements(acquisitions, item_index, currency_index)

        assert len(result) == 1
        assert result[0]["itemId"] == 400

    def test_filter_chance_salvage_no_metadata(self):
        item_index = {}
        currency_index = {}

        acquisitions = [
            {
                "type": "salvage",
                "requirementName": "Some Item",
                "requirements": [],
                "metadata": {},
            },
        ]

        result = resolver.resolve_requirements(acquisitions, item_index, currency_index)

        assert len(result) == 0


def test_strict_mode_fails_on_unresolvable():
    item_index = {"Amnytas Gear Box": [100372, 100500]}
    currency_index = {}

    acquisitions = [
        {
            "type": "pvp_reward",
            "requirements": [{"requirementName": "Amnytas Gear Box", "quantity": 1}],
        }
    ]

    with pytest.raises(ValueError, match="matches multiple IDs"):
        resolver.resolve_requirements(acquisitions, item_index, currency_index, strict=True)

    with pytest.raises(ValueError, match="matches multiple IDs"):
        resolver.resolve_requirements(acquisitions, item_index, currency_index)
