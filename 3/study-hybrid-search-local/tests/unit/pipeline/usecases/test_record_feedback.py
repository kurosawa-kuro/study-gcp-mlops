from __future__ import annotations

import pytest

from common.ports.inbound.feedback_usecase import FeedbackCommand
from pipeline.application.record_feedback import RecordFeedbackUseCase


class FakeFeedbackPort:
    def __init__(self, updated: bool = True) -> None:
        self.updated = updated
        self.calls: list[dict[str, object]] = []

    def apply_feedback(
        self,
        user_id: int | None,
        property_id: int,
        action: str,
        search_log_id: int | None,
    ) -> bool:
        self.calls.append(
            {
                "user_id": user_id,
                "property_id": property_id,
                "action": action,
                "search_log_id": search_log_id,
            }
        )
        return self.updated


def test_execute_happy_path() -> None:
    port = FakeFeedbackPort(updated=True)
    usecase = RecordFeedbackUseCase(feedback_port=port)

    result = usecase.execute(
        FeedbackCommand(
            user_id=1,
            property_id=10,
            action="favorite",
            search_log_id=100,
        )
    )

    assert result["status"] == "ok"
    assert result["property_id"] == 10
    assert result["action"] == "favorite"
    assert result["search_log_updated"] is True
    assert len(port.calls) == 1


def test_execute_without_search_log_id() -> None:
    port = FakeFeedbackPort(updated=False)
    usecase = RecordFeedbackUseCase(feedback_port=port)

    result = usecase.execute(
        FeedbackCommand(
            user_id=None,
            property_id=20,
            action="click",
            search_log_id=None,
        )
    )

    assert result["status"] == "ok"
    assert result["search_log_updated"] is False


def test_execute_raises_lookup_error_when_search_log_not_found() -> None:
    port = FakeFeedbackPort(updated=False)
    usecase = RecordFeedbackUseCase(feedback_port=port)

    with pytest.raises(LookupError):
        usecase.execute(
            FeedbackCommand(
                user_id=2,
                property_id=30,
                action="inquiry",
                search_log_id=999,
            )
        )
