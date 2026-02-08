import pytest

from gw2_data import resolver


class TestClassifyAndResolveRecipes:
    def test_recipe_crafting(self):
        item_index = {"Lump of Mithrillium": [19], "Glob of Ectoplasm": [20]}
        currency_index = {}
        node_index: set[str] = set()

        entries = [
            {
                "name": "Deldrimor Steel Ingot",
                "wikiSection": "recipe",
                "wikiSubsection": "crafting",
                "quantity": 1,
                "ingredients": [
                    {"name": "Lump of Mithrillium", "quantity": 10},
                    {"name": "Glob of Ectoplasm", "quantity": 1},
                ],
                "metadata": {"disciplines": ["Weaponsmith"], "minRating": 500},
                "confidence": 1.0,
            }
        ]

        result = resolver.classify_and_resolve(entries, item_index, currency_index, node_index)

        assert len(result) == 1
        assert result[0]["type"] == "crafting"
        assert result[0]["outputQuantity"] == 1
        assert len(result[0]["requirements"]) == 2
        assert result[0]["requirements"][0] == {"itemId": 19, "quantity": 10}
        assert result[0]["requirements"][1] == {"itemId": 20, "quantity": 1}
        assert result[0]["metadata"]["recipeType"] == "crafting"
        assert result[0]["metadata"]["disciplines"] == ["Weaponsmith"]
        assert result[0]["metadata"]["minRating"] == 500

    def test_recipe_mystic_forge(self):
        item_index = {"Item A": [1], "Item B": [2], "Item C": [3], "Item D": [4]}
        currency_index = {}
        node_index: set[str] = set()

        entries = [
            {
                "name": "Gift of Metal",
                "wikiSection": "recipe",
                "wikiSubsection": "mystic_forge",
                "quantity": 1,
                "ingredients": [
                    {"name": "Item A", "quantity": 250},
                    {"name": "Item B", "quantity": 250},
                    {"name": "Item C", "quantity": 250},
                    {"name": "Item D", "quantity": 250},
                ],
                "metadata": {},
                "confidence": 1.0,
            }
        ]

        result = resolver.classify_and_resolve(entries, item_index, currency_index, node_index)

        assert len(result) == 1
        assert result[0]["type"] == "mystic_forge"
        assert result[0]["outputQuantity"] == 1
        assert len(result[0]["requirements"]) == 4
        assert result[0]["metadata"]["recipeType"] == "mystic_forge"

    def test_recipe_with_variable_output(self):
        item_index = {"Philosopher's Stone": [76], "Mystic Crystal": [77], "Pile of Dust": [78]}
        currency_index = {}
        node_index: set[str] = set()

        entries = [
            {
                "name": "Pile of Incandescent Dust",
                "wikiSection": "recipe",
                "wikiSubsection": "mystic_forge",
                "quantity": 40,
                "quantityMin": 40,
                "quantityMax": 200,
                "ingredients": [
                    {"name": "Philosopher's Stone", "quantity": 4},
                    {"name": "Mystic Crystal", "quantity": 4},
                    {"name": "Pile of Dust", "quantity": 250},
                ],
                "metadata": {},
                "confidence": 1.0,
            }
        ]

        result = resolver.classify_and_resolve(entries, item_index, currency_index, node_index)

        assert len(result) == 1
        assert result[0]["type"] == "mystic_forge"
        assert result[0]["outputQuantity"] == 40
        assert result[0]["outputQuantityMin"] == 40
        assert result[0]["outputQuantityMax"] == 200

    def test_recipe_low_confidence_filtered(self):
        item_index = {}
        currency_index = {}
        node_index: set[str] = set()

        entries = [
            {
                "name": "Chance Recipe",
                "wikiSection": "recipe",
                "wikiSubsection": "mystic_forge",
                "quantity": 1,
                "ingredients": [],
                "metadata": {},
                "confidence": 0.4,
            }
        ]

        result = resolver.classify_and_resolve(entries, item_index, currency_index, node_index)

        assert len(result) == 0


class TestClassifyAndResolveVendor:
    def test_vendor_with_currency(self):
        item_index = {}
        currency_index = {"Fractal Relic": 7, "Coin": 1}
        node_index: set[str] = set()

        entries = [
            {
                "name": "BUY-4373",
                "wikiSection": "vendor",
                "quantity": 1,
                "ingredients": [
                    {"name": "Fractal Relic", "quantity": 30},
                    {"name": "Coin", "quantity": 9600},
                ],
                "metadata": {},
                "confidence": 1.0,
            }
        ]

        result = resolver.classify_and_resolve(entries, item_index, currency_index, node_index)

        assert len(result) == 1
        assert result[0]["type"] == "vendor"
        assert result[0]["vendorName"] == "BUY-4373"
        assert result[0]["outputQuantity"] == 1
        assert len(result[0]["requirements"]) == 2
        assert result[0]["requirements"][0] == {"currencyId": 7, "quantity": 30}
        assert result[0]["requirements"][1] == {"currencyId": 1, "quantity": 9600}

    def test_vendor_with_items(self):
        item_index = {"Grandmaster Mark": [456]}
        currency_index = {"Ascended Shards of Glory": 33, "Coin": 1}
        node_index: set[str] = set()

        entries = [
            {
                "name": "League Vendor",
                "wikiSection": "vendor",
                "quantity": 1,
                "ingredients": [
                    {"name": "Grandmaster Mark", "quantity": 5},
                    {"name": "Ascended Shards of Glory", "quantity": 350},
                    {"name": "Coin", "quantity": 20000},
                ],
                "metadata": {
                    "limitType": "daily",
                    "limitAmount": 1,
                    "notes": "Requires the skin Ardent Glorious Armguards",
                },
                "confidence": 1.0,
            }
        ]

        result = resolver.classify_and_resolve(entries, item_index, currency_index, node_index)

        assert len(result) == 1
        assert result[0]["type"] == "vendor"
        assert result[0]["vendorName"] == "League Vendor"
        assert len(result[0]["requirements"]) == 3
        assert result[0]["requirements"][0] == {"itemId": 456, "quantity": 5}
        assert result[0]["requirements"][1] == {"currencyId": 33, "quantity": 350}
        assert result[0]["requirements"][2] == {"currencyId": 1, "quantity": 20000}
        assert result[0]["metadata"]["limitType"] == "daily"
        assert result[0]["metadata"]["limitAmount"] == 1
        assert "Requires the skin" in result[0]["metadata"]["notes"]

    def test_vendor_multi_quantity(self):
        item_index = {}
        currency_index = {"Laurel": 3}
        node_index: set[str] = set()

        entries = [
            {
                "name": "Laurel Merchant",
                "wikiSection": "vendor",
                "quantity": 3,
                "ingredients": [{"name": "Laurel", "quantity": 3}],
                "metadata": {},
                "confidence": 1.0,
            }
        ]

        result = resolver.classify_and_resolve(entries, item_index, currency_index, node_index)

        assert len(result) == 1
        assert result[0]["vendorName"] == "Laurel Merchant"
        assert result[0]["outputQuantity"] == 3


class TestClassifyAndResolveGatheredFrom:
    def test_gathered_from_node(self):
        item_index = {}
        currency_index = {}
        node_index = {"Mistborn Mote node", "Rich Iron Vein"}

        entries = [
            {
                "name": "Mistborn Mote node",
                "wikiSection": "gathered_from",
                "quantity": 1,
                "quantityMin": 1,
                "quantityMax": 3,
                "ingredients": [],
                "metadata": {"guaranteed": True},
                "confidence": 0.9,
            }
        ]

        result = resolver.classify_and_resolve(entries, item_index, currency_index, node_index)

        assert len(result) == 1
        assert result[0]["type"] == "resource_node"
        assert result[0]["nodeName"] == "Mistborn Mote node"
        assert result[0]["outputQuantity"] == 1
        assert result[0]["outputQuantityMin"] == 1
        assert result[0]["outputQuantityMax"] == 3
        assert result[0]["metadata"]["guaranteed"] is True

    def test_gathered_from_container(self):
        item_index = {"Mistborn Coffer": [90783]}
        currency_index = {}
        node_index = {"Rich Iron Vein"}

        entries = [
            {
                "name": "Mistborn Coffer",
                "wikiSection": "gathered_from",
                "quantity": 1,
                "ingredients": [],
                "metadata": {"guaranteed": True},
                "confidence": 0.9,
            }
        ]

        result = resolver.classify_and_resolve(entries, item_index, currency_index, node_index)

        assert len(result) == 1
        assert result[0]["type"] == "container"
        assert result[0]["containerName"] == "Mistborn Coffer"
        assert result[0]["itemId"] == 90783
        assert result[0]["metadata"]["guaranteed"] is True

    def test_gathered_from_container_no_item_id(self):
        item_index = {}
        currency_index = {}
        node_index: set[str] = set()

        entries = [
            {
                "name": "Unknown Chest",
                "wikiSection": "gathered_from",
                "quantity": 1,
                "ingredients": [],
                "metadata": {"guaranteed": True},
                "confidence": 0.9,
            }
        ]

        result = resolver.classify_and_resolve(entries, item_index, currency_index, node_index)

        assert len(result) == 1
        assert result[0]["type"] == "container"
        assert result[0]["containerName"] == "Unknown Chest"
        assert "itemId" not in result[0]

    def test_gathered_from_chance_filtered(self):
        item_index = {}
        currency_index = {}
        node_index: set[str] = set()

        entries = [
            {
                "name": "Random Chest",
                "wikiSection": "gathered_from",
                "quantity": 1,
                "ingredients": [],
                "metadata": {"guaranteed": False, "choice": False},
                "confidence": 0.9,
            }
        ]

        result = resolver.classify_and_resolve(entries, item_index, currency_index, node_index)

        assert len(result) == 0


class TestClassifyAndResolveContainedIn:
    def test_contained_in_guaranteed(self):
        item_index = {"Bag of Obsidian": [100]}
        currency_index = {}
        node_index: set[str] = set()

        entries = [
            {
                "name": "Bag of Obsidian",
                "wikiSection": "contained_in",
                "wikiSubsection": "guaranteed",
                "quantity": 3,
                "ingredients": [],
                "metadata": {},
                "confidence": 1.0,
            }
        ]

        result = resolver.classify_and_resolve(entries, item_index, currency_index, node_index)

        assert len(result) == 1
        assert result[0]["type"] == "container"
        assert result[0]["containerName"] == "Bag of Obsidian"
        assert result[0]["itemId"] == 100
        assert result[0]["outputQuantity"] == 3
        assert result[0]["metadata"]["guaranteed"] is True

    def test_contained_in_chance_filtered(self):
        item_index = {}
        currency_index = {}
        node_index: set[str] = set()

        entries = [
            {
                "name": "Random Loot Box",
                "wikiSection": "contained_in",
                "wikiSubsection": "chance",
                "quantity": 1,
                "ingredients": [],
                "metadata": {},
                "confidence": 1.0,
            }
        ]

        result = resolver.classify_and_resolve(entries, item_index, currency_index, node_index)

        assert len(result) == 0


class TestClassifyAndResolveSalvage:
    def test_salvage_guaranteed(self):
        item_index = {"Salvageable Item": [12345]}
        currency_index = {}
        node_index: set[str] = set()

        entries = [
            {
                "name": "Salvageable Item",
                "wikiSection": "salvaged_from",
                "quantity": 1,
                "ingredients": [],
                "metadata": {"guaranteed": True},
                "confidence": 1.0,
            }
        ]

        result = resolver.classify_and_resolve(entries, item_index, currency_index, node_index)

        assert len(result) == 1
        assert result[0]["type"] == "salvage"
        assert result[0]["itemId"] == 12345
        assert result[0]["outputQuantity"] == 1

    def test_salvage_chance_filtered(self):
        item_index = {"Some Item": [999]}
        currency_index = {}
        node_index: set[str] = set()

        entries = [
            {
                "name": "Some Item",
                "wikiSection": "salvaged_from",
                "quantity": 1,
                "ingredients": [],
                "metadata": {"guaranteed": False},
                "confidence": 1.0,
            }
        ]

        result = resolver.classify_and_resolve(entries, item_index, currency_index, node_index)

        assert len(result) == 0

    def test_salvage_no_metadata_filtered(self):
        item_index = {"Some Item": [999]}
        currency_index = {}
        node_index: set[str] = set()

        entries = [
            {
                "name": "Some Item",
                "wikiSection": "salvaged_from",
                "quantity": 1,
                "ingredients": [],
                "metadata": {},
                "confidence": 1.0,
            }
        ]

        result = resolver.classify_and_resolve(entries, item_index, currency_index, node_index)

        assert len(result) == 0

    def test_salvage_unresolvable_strict_raises(self):
        item_index = {}
        currency_index = {}
        node_index: set[str] = set()

        entries = [
            {
                "name": "Unknown Item",
                "wikiSection": "salvaged_from",
                "quantity": 1,
                "ingredients": [],
                "metadata": {"guaranteed": True},
                "confidence": 1.0,
            }
        ]

        with pytest.raises(ValueError, match="Failed to resolve salvage source"):
            resolver.classify_and_resolve(
                entries, item_index, currency_index, node_index, strict=True
            )

    def test_salvage_unresolvable_lenient_skips(self):
        item_index = {}
        currency_index = {}
        node_index: set[str] = set()

        entries = [
            {
                "name": "Unknown Item",
                "wikiSection": "salvaged_from",
                "quantity": 1,
                "ingredients": [],
                "metadata": {"guaranteed": True},
                "confidence": 1.0,
            }
        ]

        result = resolver.classify_and_resolve(
            entries, item_index, currency_index, node_index, strict=False
        )

        assert len(result) == 0


class TestClassifyAndResolveAchievement:
    def test_achievement(self):
        item_index = {}
        currency_index = {}
        node_index: set[str] = set()

        entries = [
            {
                "name": "Lessons in Metallurgy",
                "wikiSection": "achievement",
                "quantity": 1,
                "ingredients": [],
                "metadata": {
                    "achievementCategory": "Collections",
                    "repeatable": False,
                    "timeGated": False,
                },
                "confidence": 1.0,
            }
        ]

        result = resolver.classify_and_resolve(entries, item_index, currency_index, node_index)

        assert len(result) == 1
        assert result[0]["type"] == "achievement"
        assert result[0]["achievementName"] == "Lessons in Metallurgy"
        assert result[0]["achievementCategory"] == "Collections"
        assert result[0]["outputQuantity"] == 1
        assert result[0]["metadata"]["repeatable"] is False
        assert result[0]["metadata"]["timeGated"] is False


class TestClassifyAndResolveRewardTrack:
    def test_reward_track_wvw(self):
        item_index = {}
        currency_index = {}
        node_index: set[str] = set()

        entries = [
            {
                "name": "Gift of Battle Item Reward Track",
                "wikiSection": "reward_track",
                "wikiSubsection": "wvw",
                "quantity": 4,
                "ingredients": [],
                "metadata": {},
                "confidence": 0.9,
            }
        ]

        result = resolver.classify_and_resolve(entries, item_index, currency_index, node_index)

        assert len(result) == 1
        assert result[0]["type"] == "wvw_reward"
        assert result[0]["trackName"] == "Gift of Battle Item Reward Track"
        assert result[0]["outputQuantity"] == 4

    def test_reward_track_pvp(self):
        item_index = {}
        currency_index = {}
        node_index: set[str] = set()

        entries = [
            {
                "name": "PvP Track",
                "wikiSection": "reward_track",
                "wikiSubsection": "pvp",
                "quantity": 2,
                "ingredients": [],
                "metadata": {},
                "confidence": 0.9,
            }
        ]

        result = resolver.classify_and_resolve(entries, item_index, currency_index, node_index)

        assert len(result) == 1
        assert result[0]["type"] == "pvp_reward"
        assert result[0]["trackName"] == "PvP Track"

    def test_reward_track_no_subsection_defaults_wvw(self):
        item_index = {}
        currency_index = {}
        node_index: set[str] = set()

        entries = [
            {
                "name": "Generic Track",
                "wikiSection": "reward_track",
                "quantity": 1,
                "ingredients": [],
                "metadata": {},
                "confidence": 0.9,
            }
        ]

        result = resolver.classify_and_resolve(entries, item_index, currency_index, node_index)

        assert len(result) == 1
        assert result[0]["type"] == "wvw_reward"


class TestClassifyAndResolveMapReward:
    def test_map_reward(self):
        item_index = {}
        currency_index = {}
        node_index: set[str] = set()

        entries = [
            {
                "name": "Gift of Exploration",
                "wikiSection": "map_reward",
                "quantity": 2,
                "ingredients": [],
                "metadata": {
                    "rewardType": "world_completion",
                    "regionName": "Central Tyria",
                    "notes": "Once per character",
                },
                "confidence": 1.0,
            }
        ]

        result = resolver.classify_and_resolve(entries, item_index, currency_index, node_index)

        assert len(result) == 1
        assert result[0]["type"] == "map_reward"
        assert result[0]["outputQuantity"] == 2
        assert result[0]["metadata"]["rewardType"] == "world_completion"
        assert result[0]["metadata"]["regionName"] == "Central Tyria"


class TestClassifyAndResolveWizardsVault:
    def test_wizards_vault(self):
        item_index = {}
        currency_index = {"Astral Acclaim": 99}
        node_index: set[str] = set()

        entries = [
            {
                "name": "Wizard's Vault",
                "wikiSection": "wizards_vault",
                "quantity": 1,
                "ingredients": [{"name": "Astral Acclaim", "quantity": 60}],
                "metadata": {"limitAmount": 20},
                "confidence": 1.0,
            }
        ]

        result = resolver.classify_and_resolve(entries, item_index, currency_index, node_index)

        assert len(result) == 1
        assert result[0]["type"] == "wizards_vault"
        assert result[0]["outputQuantity"] == 1
        assert len(result[0]["requirements"]) == 1
        assert result[0]["requirements"][0] == {"currencyId": 99, "quantity": 60}
        assert result[0]["metadata"]["limitAmount"] == 20


class TestClassifyAndResolveOther:
    def test_other(self):
        item_index = {}
        currency_index = {}
        node_index: set[str] = set()

        entries = [
            {
                "name": "Special Method",
                "wikiSection": "other",
                "quantity": 1,
                "ingredients": [],
                "metadata": {"notes": "Available through Legendary Armory"},
                "confidence": 1.0,
            }
        ]

        result = resolver.classify_and_resolve(entries, item_index, currency_index, node_index)

        assert len(result) == 1
        assert result[0]["type"] == "other"
        assert result[0]["metadata"]["notes"] == "Available through Legendary Armory"


class TestClassifyAndResolveFiltering:
    def test_confidence_threshold(self):
        item_index = {}
        currency_index = {}
        node_index: set[str] = set()

        entries = [
            {
                "name": "High Confidence",
                "wikiSection": "other",
                "quantity": 1,
                "ingredients": [],
                "metadata": {},
                "confidence": 0.95,
            },
            {
                "name": "Threshold Confidence",
                "wikiSection": "other",
                "quantity": 1,
                "ingredients": [],
                "metadata": {},
                "confidence": 0.8,
            },
            {
                "name": "Low Confidence",
                "wikiSection": "other",
                "quantity": 1,
                "ingredients": [],
                "metadata": {},
                "confidence": 0.7,
            },
        ]

        result = resolver.classify_and_resolve(entries, item_index, currency_index, node_index)

        assert len(result) == 2
        assert result[0]["type"] == "other"
        assert result[1]["type"] == "other"

    def test_unknown_section_filtered(self):
        item_index = {}
        currency_index = {}
        node_index: set[str] = set()

        entries = [
            {
                "name": "Test",
                "wikiSection": "unknown_section",
                "quantity": 1,
                "ingredients": [],
                "metadata": {},
                "confidence": 1.0,
            }
        ]

        result = resolver.classify_and_resolve(entries, item_index, currency_index, node_index)

        assert len(result) == 0


class TestClassifyAndResolveIngredientResolution:
    def test_ingredient_resolution_currency_first(self):
        item_index = {"Coin": [12345]}
        currency_index = {"Coin": 1, "Laurel": 3}
        node_index: set[str] = set()

        entries = [
            {
                "name": "Test Vendor",
                "wikiSection": "vendor",
                "quantity": 1,
                "ingredients": [
                    {"name": "Coin", "quantity": 100},
                    {"name": "Laurel", "quantity": 2},
                ],
                "metadata": {},
                "confidence": 1.0,
            }
        ]

        result = resolver.classify_and_resolve(entries, item_index, currency_index, node_index)

        assert len(result) == 1
        assert result[0]["requirements"][0]["currencyId"] == 1
        assert result[0]["requirements"][1]["currencyId"] == 3

    def test_ingredient_resolution_item_fallback(self):
        item_index = {"Item X": [777], "Item Y": [888]}
        currency_index = {}
        node_index: set[str] = set()

        entries = [
            {
                "name": "Recipe",
                "wikiSection": "recipe",
                "wikiSubsection": "crafting",
                "quantity": 1,
                "ingredients": [
                    {"name": "Item X", "quantity": 5},
                    {"name": "Item Y", "quantity": 10},
                ],
                "metadata": {},
                "confidence": 1.0,
            }
        ]

        result = resolver.classify_and_resolve(entries, item_index, currency_index, node_index)

        assert len(result) == 1
        assert result[0]["requirements"][0]["itemId"] == 777
        assert result[0]["requirements"][1]["itemId"] == 888

    def test_unresolvable_ingredient_strict_raises(self):
        item_index = {}
        currency_index = {}
        node_index: set[str] = set()

        entries = [
            {
                "name": "Test Recipe",
                "wikiSection": "recipe",
                "wikiSubsection": "crafting",
                "quantity": 1,
                "ingredients": [{"name": "Unknown Item", "quantity": 1}],
                "metadata": {},
                "confidence": 1.0,
            }
        ]

        with pytest.raises(ValueError, match="Failed to resolve ingredient"):
            resolver.classify_and_resolve(
                entries, item_index, currency_index, node_index, strict=True
            )

    def test_unresolvable_ingredient_lenient_skips(self):
        item_index = {}
        currency_index = {}
        node_index: set[str] = set()

        entries = [
            {
                "name": "Test Recipe",
                "wikiSection": "recipe",
                "wikiSubsection": "crafting",
                "quantity": 1,
                "ingredients": [{"name": "Unknown Item", "quantity": 1}],
                "metadata": {},
                "confidence": 1.0,
            }
        ]

        result = resolver.classify_and_resolve(
            entries, item_index, currency_index, node_index, strict=False
        )

        assert len(result) == 0


class TestClassifyAndResolveMultipleEntries:
    def test_mixed_entries(self):
        item_index = {"Item A": [1], "Mistborn Coffer": [90783]}
        currency_index = {"Coin": 1}
        node_index = {"Mistborn Mote node"}

        entries = [
            {
                "name": "Recipe Output",
                "wikiSection": "recipe",
                "wikiSubsection": "crafting",
                "quantity": 1,
                "ingredients": [{"name": "Item A", "quantity": 1}],
                "metadata": {},
                "confidence": 1.0,
            },
            {
                "name": "Vendor NPC",
                "wikiSection": "vendor",
                "quantity": 1,
                "ingredients": [{"name": "Coin", "quantity": 5000}],
                "metadata": {},
                "confidence": 1.0,
            },
            {
                "name": "Mistborn Mote node",
                "wikiSection": "gathered_from",
                "quantity": 1,
                "ingredients": [],
                "metadata": {"guaranteed": True},
                "confidence": 0.9,
            },
            {
                "name": "Mistborn Coffer",
                "wikiSection": "gathered_from",
                "quantity": 1,
                "ingredients": [],
                "metadata": {"guaranteed": True},
                "confidence": 0.9,
            },
        ]

        result = resolver.classify_and_resolve(entries, item_index, currency_index, node_index)

        assert len(result) == 4
        assert result[0]["type"] == "crafting"
        assert result[1]["type"] == "vendor"
        assert result[2]["type"] == "resource_node"
        assert result[3]["type"] == "container"
