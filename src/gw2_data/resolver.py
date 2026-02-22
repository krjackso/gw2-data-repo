import logging
from typing import Any

from gw2_data import api
from gw2_data.exceptions import APIError, MultipleItemMatchError

log = logging.getLogger(__name__)


def _resolve_ingredient_list(
    ingredients: list[dict[str, Any]],
    item_name_index: dict[str, list[int]],
    currency_name_index: dict[str, int],
    strict: bool,
    current_item_id: int = 0,
) -> list[dict[str, Any]] | None:
    resolved = []
    for ingredient in ingredients:
        name = ingredient["name"]
        quantity = ingredient["quantity"]

        currency_id = None
        try:
            currency_id = api.resolve_currency_name_to_id(name, currency_name_index)
        except (APIError, KeyError):
            pass

        if currency_id is not None:
            resolved.append({"currencyId": currency_id, "quantity": quantity})
        else:
            try:
                resolved_item_id = api.resolve_item_name_to_id(name, item_name_index)
                resolved.append({"itemId": resolved_item_id, "quantity": quantity})
            except MultipleItemMatchError as e:
                if current_item_id in e.item_ids:
                    remaining = [mid for mid in e.item_ids if mid != current_item_id]
                    if len(remaining) == 1:
                        log.info(
                            f"Disambiguated '{name}': excluded self-reference ({current_item_id}), "
                            f"resolved to {remaining[0]}"
                        )
                        resolved.append({"itemId": remaining[0], "quantity": quantity})
                        continue

                if not strict:
                    log.warning(f"Skipping unresolvable ingredient '{name}': {e}")
                    return None
                overrides = "src/gw2_data/overrides/item_name_overrides.yaml"
                raise ValueError(
                    f"Failed to resolve ingredient '{name}' "
                    f"(matches multiple IDs: {e.item_ids}). "
                    f"If this is a known variant, add to {overrides}: {e}"
                ) from e
            except (APIError, KeyError) as e:
                if not strict:
                    log.warning(f"Skipping unresolvable ingredient '{name}': {e}")
                    return None
                raise ValueError(
                    f"Failed to resolve ingredient '{name}' "
                    f"(not found in currency or item index). "
                    f"Add to overrides: {e}"
                ) from e

    return resolved


def _classify_entry(
    entry: dict[str, Any],
    item_name_index: dict[str, list[int]],
    currency_name_index: dict[str, int],
    gathering_node_index: set[str],
    strict: bool,
    current_item_id: int = 0,
) -> dict[str, Any] | None:
    wiki_section = entry["wikiSection"]
    wiki_subsection = entry.get("wikiSubsection")
    name = entry["name"]
    quantity = entry.get("quantity", 1)
    quantity_min = entry.get("quantityMin")
    quantity_max = entry.get("quantityMax")
    ingredients = entry.get("ingredients", [])
    metadata = entry.get("metadata", {})
    guaranteed = entry.get("guaranteed")
    choice = entry.get("choice")

    if wiki_section == "recipe":
        if wiki_subsection == "mystic_forge":
            acq_type = "mystic_forge"
            recipe_type = "mystic_forge"
        else:
            acq_type = "crafting"
            recipe_type = "crafting"

        requirements = _resolve_ingredient_list(
            ingredients, item_name_index, currency_name_index, strict, current_item_id
        )
        if requirements is None:
            return None

        acq: dict[str, Any] = {
            "type": acq_type,
            "outputQuantity": quantity,
            "requirements": requirements,
            "metadata": {"recipeType": recipe_type, **metadata},
        }

        if quantity_min is not None:
            acq["outputQuantityMin"] = quantity_min
        if quantity_max is not None:
            acq["outputQuantityMax"] = quantity_max

        return acq

    if wiki_section == "vendor":
        requirements = _resolve_ingredient_list(
            ingredients, item_name_index, currency_name_index, strict, current_item_id
        )
        if requirements is None:
            return None

        return {
            "type": "vendor",
            "vendorName": name,
            "outputQuantity": quantity,
            "requirements": requirements,
            "metadata": metadata,
        }

    if wiki_section == "gathered_from":
        cleaned_name = api.clean_name(name)

        if cleaned_name in gathering_node_index:
            acq_type = "resource_node"
            acq = {
                "type": acq_type,
                "nodeName": name,
                "outputQuantity": quantity,
                "requirements": [],
                "metadata": metadata,
            }
        else:
            acq_type = "container"
            acq = {
                "type": acq_type,
                "containerName": name,
                "outputQuantity": quantity,
                "requirements": [],
                "metadata": metadata,
            }
            container_variant = f"{name} (container)"
            resolve_name = (
                container_variant if api.clean_name(container_variant) in item_name_index else name
            )
            try:
                acq["itemId"] = api.resolve_item_name_to_id(resolve_name, item_name_index)
            except (APIError, KeyError) as e:
                log.info(f"Container '{name}' has no item ID: {e}")

        if guaranteed is not None:
            acq["guaranteed"] = guaranteed
        if choice is not None:
            acq["choice"] = choice

        if acq.get("guaranteed") is False and acq.get("choice") is False:
            log.info(f"Excluding chance-based {acq_type} from gathered_from: {name}")
            return None

        if quantity_min is not None:
            acq["outputQuantityMin"] = quantity_min
        if quantity_max is not None:
            acq["outputQuantityMax"] = quantity_max

        return acq

    if wiki_section == "contained_in":
        if wiki_subsection == "chance":
            log.info(f"Excluding chance-based container from contained_in: {name}")
            return None

        acq = {
            "type": "container",
            "containerName": name,
            "outputQuantity": quantity,
            "requirements": [],
            "metadata": metadata,
        }

        if wiki_subsection == "guaranteed":
            acq["guaranteed"] = True
        elif wiki_subsection == "inline":
            if guaranteed is not None:
                acq["guaranteed"] = guaranteed
            if choice is not None:
                acq["choice"] = choice

            if acq.get("guaranteed") is False and acq.get("choice") is False:
                log.info(f"Excluding chance-based container from contained_in: {name}")
                return None

        container_variant = f"{name} (container)"
        resolve_name = (
            container_variant if api.clean_name(container_variant) in item_name_index else name
        )
        try:
            acq["itemId"] = api.resolve_item_name_to_id(resolve_name, item_name_index)
        except (APIError, KeyError) as e:
            log.info(f"Container '{name}' has no item ID: {e}")

        if quantity_min is not None:
            acq["outputQuantityMin"] = quantity_min
        if quantity_max is not None:
            acq["outputQuantityMax"] = quantity_max

        return acq

    if wiki_section == "salvaged_from":
        if not guaranteed:
            log.info(f"Excluding chance-based salvage: {name}")
            return None

        cleaned_name = api.clean_name(name)
        matches = item_name_index.get(cleaned_name)

        if not matches:
            if not strict:
                log.warning(f"Skipping unresolvable salvage source '{name}': not found in index")
                return None
            overrides = "src/gw2_data/overrides/item_name_overrides.yaml"
            raise ValueError(
                f"Failed to resolve salvage source '{name}' "
                f"(not found in item index). "
                f"If this is a known variant, add to {overrides}"
            )

        acq = {
            "type": "salvage",
            "itemIds": matches,
            "outputQuantity": quantity,
            "requirements": [],
            "metadata": metadata,
        }

        if guaranteed is not None:
            acq["guaranteed"] = guaranteed

        return acq

    if wiki_section == "achievement":
        return {
            "type": "achievement",
            "achievementName": name,
            "achievementCategory": metadata.get("achievementCategory"),
            "outputQuantity": quantity,
            "requirements": [],
            "metadata": {k: v for k, v in metadata.items() if k not in ("achievementCategory",)},
        }

    if wiki_section == "reward_track":
        if wiki_subsection == "wvw":
            acq_type = "wvw_reward"
        elif wiki_subsection == "pvp":
            acq_type = "pvp_reward"
        else:
            acq_type = "wvw_reward"

        return {
            "type": acq_type,
            "trackName": name,
            "outputQuantity": quantity,
            "requirements": [],
            "metadata": metadata,
        }

    if wiki_section == "map_reward":
        return {
            "type": "map_reward",
            "outputQuantity": quantity,
            "requirements": [],
            "metadata": metadata,
        }

    if wiki_section == "wizards_vault":
        requirements = _resolve_ingredient_list(
            ingredients, item_name_index, currency_name_index, strict, current_item_id
        )
        if requirements is None:
            return None

        return {
            "type": "wizards_vault",
            "outputQuantity": quantity,
            "requirements": requirements,
            "metadata": metadata,
        }

    if wiki_section == "other":
        return {
            "type": "other",
            "outputQuantity": quantity,
            "requirements": [],
            "metadata": metadata,
        }

    log.warning(f"Unknown wiki section '{wiki_section}' for entry: {name}")
    return None


def classify_and_resolve(
    raw_entries: list[dict[str, Any]],
    item_name_index: dict[str, list[int]],
    currency_name_index: dict[str, int],
    gathering_node_index: set[str],
    strict: bool = True,
    current_item_id: int = 0,
) -> list[dict[str, Any]]:
    acquisitions = []

    for entry in raw_entries:
        confidence = entry.get("confidence", 0.0)
        if confidence < 0.8:
            name = entry.get("name", "unknown")
            log.info(f"Excluding low-confidence entry ({confidence:.0%}): {name}")
            continue

        acq = _classify_entry(
            entry,
            item_name_index,
            currency_name_index,
            gathering_node_index,
            strict,
            current_item_id,
        )
        if acq is not None:
            if acq["type"] == "salvage":
                item_ids = acq.pop("itemIds")
                for item_id in item_ids:
                    salvage_acq = {**acq, "itemId": item_id}
                    if "metadata" in acq:
                        salvage_acq["metadata"] = {**acq["metadata"]}
                    acquisitions.append(salvage_acq)
            else:
                acquisitions.append(acq)

    return acquisitions
