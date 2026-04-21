from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SearchQueryDTO:
    q: str = ""
    user_id: int | None = None
    city: str | None = None
    layout: str | None = None
    price_lte: int | None = None
    pet: bool | None = None
    walk_min: int | None = None
    limit: int = 20
    candidate_limit: int = 100
