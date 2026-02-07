from gw2_data import api


def resolve_requirements(
    acquisitions: list[dict],
    item_name_index: dict[str, list[int]],
    currency_name_index: dict[str, int],
) -> list[dict]:
    resolved = []
    for acq in acquisitions:
        acq_copy = dict(acq)
        requirements = acq_copy.get("requirements", [])
        resolved_reqs = []

        for req in requirements:
            req_copy = dict(req)

            if "itemName" in req_copy:
                item_name = req_copy.pop("itemName")
                try:
                    item_id = api.resolve_item_name_to_id(item_name, item_name_index)
                    req_copy["itemId"] = item_id
                except Exception as e:
                    acq_type = acq["type"]
                    raise ValueError(
                        f"Failed to resolve item '{item_name}' in {acq_type} acquisition: {e}"
                    ) from e

            if "currencyName" in req_copy:
                currency_name = req_copy.pop("currencyName")
                try:
                    currency_id = api.resolve_currency_name_to_id(
                        currency_name, currency_name_index
                    )
                    req_copy["currencyId"] = currency_id
                except Exception as e:
                    acq_type = acq["type"]
                    msg = f"Failed to resolve currency '{currency_name}' in {acq_type} acquisition"
                    raise ValueError(f"{msg}: {e}") from e

            resolved_reqs.append(req_copy)

        acq_copy["requirements"] = resolved_reqs
        resolved.append(acq_copy)

    return resolved
