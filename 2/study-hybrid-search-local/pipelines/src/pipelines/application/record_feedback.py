from __future__ import annotations

from dataclasses import dataclass

from common.ports.inbound.feedback_usecase import FeedbackCommand
from common.ports.outbound.feedback_port import FeedbackPort


@dataclass
class RecordFeedbackUseCase:
    feedback_port: FeedbackPort

    def execute(self, command: FeedbackCommand) -> dict[str, object]:
        updated_search_log = self.feedback_port.apply_feedback(
            user_id=command.user_id,
            property_id=command.property_id,
            action=command.action,
            search_log_id=command.search_log_id,
        )

        if command.search_log_id is not None and not updated_search_log:
            raise LookupError("search_log_id not found")

        return {
            "status": "ok",
            "property_id": command.property_id,
            "action": command.action,
            "search_log_updated": updated_search_log,
        }
