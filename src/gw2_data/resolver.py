import logging

from gw2_data import api
from gw2_data.exceptions import APIError

log = logging.getLogger(__name__)


def resolve_requirements(
    acquisitions: list[dict],
    item_name_index: dict[str, list[int]],
    currency_name_index: dict[str, int],
) -> list[dict]:
    resolved = []
    for acq in acquisitions:
        if acq.get("discontinued"):
            log.info(f"Excluding discontinued {acq['type']} acquisition")
            continue
        acq_copy = dict(acq)
        requirements = acq_copy.get("requirements", [])
        resolved_reqs = []

        for req in requirements:
            req_copy = dict(req)

            if "requirementName" in req_copy:
                name = req_copy.pop("requirementName")
                acq_type = acq["type"]

                currency_id = None
                try:
                    currency_id = api.resolve_currency_name_to_id(name, currency_name_index)
                    req_copy["currencyId"] = currency_id
                except (APIError, KeyError):
                    pass

                if currency_id is None:
                    try:
                        item_id = api.resolve_item_name_to_id(name, item_name_index)
                        req_copy["itemId"] = item_id
                    except (APIError, KeyError) as e:
                        raise ValueError(
                            f"Failed to resolve requirement '{name}' in {acq_type} acquisition "
                            f"(not found in currency or item index). "
                            f"If this is a known variant, add to currency_name_overrides.yaml "
                            f"or item_name_overrides.yaml. "
                            f"If this acquisition is discontinued, the LLM should mark it with "
                            f"discontinued: true and it will be excluded: {e}"
                        ) from e

            resolved_reqs.append(req_copy)

        acq_copy["requirements"] = resolved_reqs
        resolved.append(acq_copy)

    return resolved
