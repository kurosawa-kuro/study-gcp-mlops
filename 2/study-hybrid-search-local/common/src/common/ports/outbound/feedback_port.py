from __future__ import annotations

from typing import Literal, Protocol

FeedbackAction = Literal["click", "favorite", "inquiry"]


class FeedbackPort(Protocol):
    def apply_feedback(
        self,
        user_id: int | None,
        property_id: int,
        action: FeedbackAction,
        search_log_id: int | None,
    ) -> bool:
        ...
