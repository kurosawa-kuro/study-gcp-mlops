"""``FeedbackRecorder`` Port — user-feedback ingestion from /feedback."""

from __future__ import annotations

from typing import Protocol


class FeedbackRecorder(Protocol):
    """Writes a single feedback event to the log sink."""

    def record(self, *, request_id: str, property_id: str, action: str) -> None: ...
