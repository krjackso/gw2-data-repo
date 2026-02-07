"""
Tests for acquisition and requirement sorting logic.

Validates that acquisitions are sorted deterministically by:
- Type priority (crafting → vendor → achievement → ...)
- Type-specific metadata fields
- Discontinued status
- Output quantity

Also verifies requirements are sorted by ID within each acquisition.
"""

from gw2_data import sorter


class TestSortAcquisitions:
    def test_sort_by_type_priority(self):
        acquisitions = [
            {"type": "vendor", "outputQuantity": 1, "requirements": []},
            {"type": "crafting", "outputQuantity": 1, "requirements": []},
            {"type": "achievement", "outputQuantity": 1, "requirements": []},
        ]

        result = sorter.sort_acquisitions(acquisitions)

        assert result[0]["type"] == "crafting"
        assert result[1]["type"] == "vendor"
        assert result[2]["type"] == "achievement"

    def test_sort_unknown_type_last(self):
        acquisitions = [
            {"type": "vendor", "outputQuantity": 1, "requirements": []},
            {"type": "unknown_type", "outputQuantity": 1, "requirements": []},
            {"type": "crafting", "outputQuantity": 1, "requirements": []},
        ]

        result = sorter.sort_acquisitions(acquisitions)

        assert result[0]["type"] == "crafting"
        assert result[1]["type"] == "vendor"
        assert result[2]["type"] == "unknown_type"

    def test_sort_empty_list(self):
        result = sorter.sort_acquisitions([])
        assert result == []

    def test_sort_preserves_all_fields(self):
        acquisitions = [
            {
                "type": "vendor",
                "vendorName": "Test Vendor",
                "outputQuantity": 5,
                "discontinued": True,
                "requirements": [{"itemId": 123, "quantity": 1}],
                "metadata": {"limitType": "daily"},
            }
        ]

        result = sorter.sort_acquisitions(acquisitions)

        assert len(result) == 1
        assert result[0]["type"] == "vendor"
        assert result[0]["vendorName"] == "Test Vendor"
        assert result[0]["outputQuantity"] == 5
        assert result[0]["discontinued"] is True
        assert result[0]["metadata"] == {"limitType": "daily"}


class TestSortByMetadata:
    def test_sort_crafting_by_min_rating(self):
        acquisitions = [
            {
                "type": "crafting",
                "outputQuantity": 1,
                "requirements": [],
                "metadata": {"minRating": 500},
            },
            {
                "type": "crafting",
                "outputQuantity": 1,
                "requirements": [],
                "metadata": {"minRating": 400},
            },
            {
                "type": "crafting",
                "outputQuantity": 1,
                "requirements": [],
                "metadata": {"minRating": 450},
            },
        ]

        result = sorter.sort_acquisitions(acquisitions)

        assert result[0]["metadata"]["minRating"] == 400
        assert result[1]["metadata"]["minRating"] == 450
        assert result[2]["metadata"]["minRating"] == 500

    def test_sort_crafting_by_discipline(self):
        acquisitions = [
            {
                "type": "crafting",
                "outputQuantity": 1,
                "requirements": [],
                "metadata": {"minRating": 400, "disciplines": ["Weaponsmith"]},
            },
            {
                "type": "crafting",
                "outputQuantity": 1,
                "requirements": [],
                "metadata": {"minRating": 400, "disciplines": ["Armorsmith"]},
            },
        ]

        result = sorter.sort_acquisitions(acquisitions)

        assert result[0]["metadata"]["disciplines"][0] == "Armorsmith"
        assert result[1]["metadata"]["disciplines"][0] == "Weaponsmith"

    def test_sort_vendor_by_name(self):
        acquisitions = [
            {
                "type": "vendor",
                "vendorName": "Zephyr Vendor",
                "outputQuantity": 1,
                "requirements": [],
            },
            {
                "type": "vendor",
                "vendorName": "Alpha Vendor",
                "outputQuantity": 1,
                "requirements": [],
            },
            {
                "type": "vendor",
                "vendorName": "Beta Vendor",
                "outputQuantity": 1,
                "requirements": [],
            },
        ]

        result = sorter.sort_acquisitions(acquisitions)

        assert result[0]["vendorName"] == "Alpha Vendor"
        assert result[1]["vendorName"] == "Beta Vendor"
        assert result[2]["vendorName"] == "Zephyr Vendor"

    def test_sort_container_guaranteed_first(self):
        acquisitions = [
            {
                "type": "container",
                "outputQuantity": 1,
                "requirements": [],
                "metadata": {"guaranteed": False, "containerItemId": 200},
            },
            {
                "type": "container",
                "outputQuantity": 1,
                "requirements": [],
                "metadata": {"guaranteed": True, "containerItemId": 100},
            },
            {
                "type": "container",
                "outputQuantity": 1,
                "requirements": [],
                "metadata": {"guaranteed": True, "containerItemId": 150},
            },
        ]

        result = sorter.sort_acquisitions(acquisitions)

        assert result[0]["metadata"]["guaranteed"] is True
        assert result[0]["metadata"]["containerItemId"] == 100
        assert result[1]["metadata"]["guaranteed"] is True
        assert result[1]["metadata"]["containerItemId"] == 150
        assert result[2]["metadata"]["guaranteed"] is False

    def test_sort_achievement_by_name(self):
        acquisitions = [
            {
                "type": "achievement",
                "outputQuantity": 1,
                "requirements": [],
                "metadata": {"achievementName": "Zeta Achievement"},
            },
            {
                "type": "achievement",
                "outputQuantity": 1,
                "requirements": [],
                "metadata": {"achievementName": "Alpha Achievement"},
            },
        ]

        result = sorter.sort_acquisitions(acquisitions)

        assert result[0]["metadata"]["achievementName"] == "Alpha Achievement"
        assert result[1]["metadata"]["achievementName"] == "Zeta Achievement"


class TestSortByDiscontinued:
    def test_sort_active_before_discontinued(self):
        acquisitions = [
            {
                "type": "vendor",
                "vendorName": "Test",
                "discontinued": True,
                "outputQuantity": 1,
                "requirements": [],
            },
            {
                "type": "vendor",
                "vendorName": "Test",
                "outputQuantity": 1,
                "requirements": [],
            },
            {
                "type": "vendor",
                "vendorName": "Test",
                "discontinued": False,
                "outputQuantity": 1,
                "requirements": [],
            },
        ]

        result = sorter.sort_acquisitions(acquisitions)

        assert result[0].get("discontinued") is None
        assert result[1].get("discontinued") is False
        assert result[2]["discontinued"] is True


class TestSortByOutputQuantity:
    def test_sort_by_output_quantity(self):
        acquisitions = [
            {
                "type": "vendor",
                "vendorName": "Test",
                "outputQuantity": 10,
                "requirements": [],
            },
            {
                "type": "vendor",
                "vendorName": "Test",
                "outputQuantity": 1,
                "requirements": [],
            },
            {
                "type": "vendor",
                "vendorName": "Test",
                "outputQuantity": 5,
                "requirements": [],
            },
        ]

        result = sorter.sort_acquisitions(acquisitions)

        assert result[0]["outputQuantity"] == 1
        assert result[1]["outputQuantity"] == 5
        assert result[2]["outputQuantity"] == 10


class TestSortRequirements:
    def test_sort_items_before_currencies(self):
        requirements = [
            {"currencyId": 1, "quantity": 100},
            {"itemId": 123, "quantity": 5},
            {"itemId": 456, "quantity": 2},
            {"currencyId": 2, "quantity": 50},
        ]

        result = sorter.sort_requirements(requirements)

        assert result[0] == {"itemId": 123, "quantity": 5}
        assert result[1] == {"itemId": 456, "quantity": 2}
        assert result[2] == {"currencyId": 1, "quantity": 100}
        assert result[3] == {"currencyId": 2, "quantity": 50}

    def test_sort_items_by_id(self):
        requirements = [
            {"itemId": 456, "quantity": 1},
            {"itemId": 123, "quantity": 1},
            {"itemId": 789, "quantity": 1},
        ]

        result = sorter.sort_requirements(requirements)

        assert result[0]["itemId"] == 123
        assert result[1]["itemId"] == 456
        assert result[2]["itemId"] == 789

    def test_sort_currencies_by_id(self):
        requirements = [
            {"currencyId": 3, "quantity": 100},
            {"currencyId": 1, "quantity": 100},
            {"currencyId": 2, "quantity": 100},
        ]

        result = sorter.sort_requirements(requirements)

        assert result[0]["currencyId"] == 1
        assert result[1]["currencyId"] == 2
        assert result[2]["currencyId"] == 3

    def test_sort_empty_requirements(self):
        result = sorter.sort_requirements([])
        assert result == []


class TestEdgeCases:
    def test_missing_metadata_fields(self):
        acquisitions = [
            {"type": "crafting", "outputQuantity": 1, "requirements": []},
            {
                "type": "crafting",
                "outputQuantity": 1,
                "requirements": [],
                "metadata": {},
            },
        ]

        result = sorter.sort_acquisitions(acquisitions)
        assert len(result) == 2

    def test_missing_vendor_name(self):
        acquisitions = [
            {"type": "vendor", "outputQuantity": 1, "requirements": []},
            {
                "type": "vendor",
                "vendorName": "Test",
                "outputQuantity": 1,
                "requirements": [],
            },
        ]

        result = sorter.sort_acquisitions(acquisitions)

        assert result[0].get("vendorName") is None
        assert result[1]["vendorName"] == "Test"

    def test_empty_disciplines_list(self):
        acquisitions = [
            {
                "type": "crafting",
                "outputQuantity": 1,
                "requirements": [],
                "metadata": {"disciplines": []},
            }
        ]

        result = sorter.sort_acquisitions(acquisitions)
        assert len(result) == 1

    def test_array_index_out_of_bounds(self):
        acquisitions = [
            {
                "type": "crafting",
                "outputQuantity": 1,
                "requirements": [],
                "metadata": {"disciplines": []},
            },
            {
                "type": "crafting",
                "outputQuantity": 1,
                "requirements": [],
                "metadata": {"disciplines": ["Weaponsmith"]},
            },
        ]

        result = sorter.sort_acquisitions(acquisitions)

        assert len(result) == 2

    def test_nested_none_values(self):
        acquisitions = [
            {
                "type": "container",
                "outputQuantity": 1,
                "requirements": [],
                "metadata": {"guaranteed": None, "containerItemId": None},
            }
        ]

        result = sorter.sort_acquisitions(acquisitions)
        assert len(result) == 1


class TestComplexScenarios:
    def test_zap_example(self):
        """Test realistic example from Zap item with multiple containers"""
        acquisitions = [
            {
                "type": "container",
                "discontinued": True,
                "outputQuantity": 1,
                "requirements": [{"itemId": 67410, "quantity": 1}],
                "metadata": {"guaranteed": False, "choice": True, "containerItemId": 67410},
            },
            {
                "type": "container",
                "outputQuantity": 1,
                "requirements": [{"itemId": 88590, "quantity": 1}],
                "metadata": {"guaranteed": True, "choice": False, "containerItemId": 88590},
            },
            {
                "type": "crafting",
                "outputQuantity": 1,
                "requirements": [
                    {"itemId": 46741, "quantity": 1},
                    {"itemId": 46744, "quantity": 1},
                    {"itemId": 46745, "quantity": 1},
                    {"itemId": 46746, "quantity": 1},
                ],
                "metadata": {
                    "recipeType": "crafting",
                    "disciplines": ["Weaponsmith"],
                    "minRating": 500,
                },
            },
            {
                "type": "container",
                "outputQuantity": 1,
                "requirements": [{"itemId": 82898, "quantity": 1}],
                "metadata": {"guaranteed": False, "choice": True, "containerItemId": 82898},
            },
        ]

        result = sorter.sort_acquisitions(acquisitions)

        assert result[0]["type"] == "crafting"
        assert result[1]["type"] == "container"
        assert result[1]["metadata"]["guaranteed"] is True
        assert result[1]["metadata"]["containerItemId"] == 88590
        assert result[2]["type"] == "container"
        assert result[2]["metadata"]["guaranteed"] is False
        assert result[2]["metadata"]["containerItemId"] == 67410
        assert result[2]["discontinued"] is True
        assert result[3]["type"] == "container"
        assert result[3]["metadata"]["guaranteed"] is False
        assert result[3]["metadata"]["containerItemId"] == 82898
        assert result[3].get("discontinued") is not True

    def test_requirements_sorting_within_acquisition(self):
        """Test that requirements are sorted within each acquisition"""
        acquisitions = [
            {
                "type": "crafting",
                "outputQuantity": 1,
                "requirements": [
                    {"itemId": 456, "quantity": 2},
                    {"currencyId": 1, "quantity": 100},
                    {"itemId": 123, "quantity": 1},
                ],
            }
        ]

        result = sorter.sort_acquisitions(acquisitions)

        reqs = result[0]["requirements"]
        assert reqs[0]["itemId"] == 123
        assert reqs[1]["itemId"] == 456
        assert reqs[2]["currencyId"] == 1


class TestParseFieldPath:
    def test_simple_path(self):
        result = sorter._parse_field_path("metadata.minRating")
        assert result == ["metadata", "minRating"]

    def test_nested_path(self):
        result = sorter._parse_field_path("a.b.c.d")
        assert result == ["a", "b", "c", "d"]

    def test_array_index_path(self):
        result = sorter._parse_field_path("metadata.disciplines[0]")
        assert result == ["metadata", "disciplines", 0]

    def test_multiple_array_indices(self):
        result = sorter._parse_field_path("items[0].nested[1]")
        assert result == ["items", 0, "nested", 1]


class TestExtractFieldValue:
    def test_extract_simple_field(self):
        data = {"name": "test"}
        result = sorter._extract_field_value(data, "name")
        assert result == "test"

    def test_extract_nested_field(self):
        data = {"metadata": {"minRating": 500}}
        result = sorter._extract_field_value(data, "metadata.minRating")
        assert result == 500

    def test_extract_array_element(self):
        data = {"metadata": {"disciplines": ["Weaponsmith", "Armorsmith"]}}
        result = sorter._extract_field_value(data, "metadata.disciplines[0]")
        assert result == "Weaponsmith"

    def test_extract_missing_field(self):
        data = {"name": "test"}
        result = sorter._extract_field_value(data, "missing")
        assert result is None

    def test_extract_array_out_of_bounds(self):
        data = {"items": [1, 2]}
        result = sorter._extract_field_value(data, "items[5]")
        assert result is None

    def test_extract_from_none(self):
        data = {"metadata": None}
        result = sorter._extract_field_value(data, "metadata.minRating")
        assert result is None
