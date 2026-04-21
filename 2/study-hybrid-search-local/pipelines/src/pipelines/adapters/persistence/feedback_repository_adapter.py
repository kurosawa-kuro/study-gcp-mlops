from __future__ import annotations

from common.ports.outbound.feedback_port import FeedbackAction
from pipelines.repositories.search_log_repository import apply_feedback


class FeedbackRepositoryAdapter:
    def apply_feedback(
        self,
        user_id: int | None,
        property_id: int,
        action: FeedbackAction,
        search_log_id: int | None,
    ) -> bool:
        return apply_feedback(
            user_id=user_id,
            property_id=property_id,
            action=action,
            search_log_id=search_log_id,
        )
