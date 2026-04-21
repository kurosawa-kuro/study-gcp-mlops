from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

FeedbackAction = Literal["click", "favorite", "inquiry"]


@dataclass
class FeedbackCommandDTO:
    user_id: int | None
    property_id: int
    action: FeedbackAction
    search_log_id: int | None
