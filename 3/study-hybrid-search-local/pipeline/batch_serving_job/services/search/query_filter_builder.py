from typing import Any


def _quote(value: str) -> str:
    return '"' + value.replace('"', '\\"') + '"'


def build_search_payload(
    q: str,
    city: str | None,
    layout: str | None,
    price_lte: int | None,
    pet: bool | None,
    walk_min: int | None,
    candidate_limit: int = 100,
) -> dict[str, Any]:
    filters: list[str] = []

    if city:
        filters.append(f"city = {_quote(city)}")
    if layout:
        filters.append(f"layout = {_quote(layout)}")
    if price_lte is not None:
        filters.append(f"price <= {price_lte}")
    if pet is not None:
        filters.append(f"pet = {'true' if pet else 'false'}")
    if walk_min is not None:
        filters.append(f"walk_min <= {walk_min}")

    payload: dict[str, Any] = {
        "q": q,
        "limit": candidate_limit,
    }

    if filters:
        payload["filter"] = filters

    return payload
