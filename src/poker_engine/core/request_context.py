"""RequestContext: metadata tying a Slow Path request to a specific state.

Used by Solver Adapter / Poker Reasoning Adapter to tag async requests so the
Orchestrator can later discard stale results. This task ONLY defines the
object — stale result filtering logic belongs to the Orchestrator in a
later task.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ._freeze import _require_aware_dt


@dataclass(frozen=True)
class RequestContext:
    """Identifies which hand/state_version a Slow Path request belongs to."""

    hand_id: str
    state_version: int
    request_id: str
    requested_at: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.hand_id, str) or not self.hand_id:
            raise ValueError("hand_id must be a non-empty str")
        if not isinstance(self.state_version, int) or isinstance(
            self.state_version, bool
        ):
            raise TypeError("state_version must be an int")
        if self.state_version < 0:
            raise ValueError("state_version must be >= 0")
        if not isinstance(self.request_id, str) or not self.request_id:
            raise ValueError("request_id must be a non-empty str")
        if not isinstance(self.requested_at, datetime):
            raise TypeError("requested_at must be a datetime")
        _require_aware_dt(self.requested_at)


__all__ = ["RequestContext"]
