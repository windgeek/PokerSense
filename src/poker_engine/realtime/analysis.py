"""Realtime analysis output contract.

The realtime layer's observable product is a :class:`RealtimeAnalysis` snapshot:
current state + equity (win_rate / tie_rate) + confidence. This is a pure data
value — deliberately NOT strategy advice (no fold/call/raise, no bet sizing,
no outs). Those belong to later tasks built on top of a stable state + reliable
equity + opponent model.
"""

from __future__ import annotations

from dataclasses import dataclass

from poker_engine.core.enums import Street
from poker_engine.core.observation import RawObservation
from poker_engine.core.state import PokerState
from poker_engine.core.value_objects import Card, ChipAmount


@dataclass(frozen=True)
class StateSnapshot:
    """Immutable, serialization-safe view of the current canonical state."""

    street: Street
    hero_cards: tuple[Card, ...]
    board_cards: tuple[Card, ...]
    pot: ChipAmount

    @classmethod
    def from_state(cls, state: PokerState) -> "StateSnapshot":
        if not isinstance(state, PokerState):
            raise TypeError("state must be a PokerState")
        return cls(
            street=state.street,
            hero_cards=tuple(state.hero_cards),
            board_cards=tuple(state.board_cards),
            pot=state.pot,
        )


@dataclass(frozen=True)
class EquitySnapshot:
    """Hero equity snapshot (win_rate + tie_rate only, per Task 8 boundary)."""

    win_rate: float
    tie_rate: float

    def __post_init__(self) -> None:
        for name in ("win_rate", "tie_rate"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise TypeError(f"{name} must be a float")
            if not (0.0 <= float(v) <= 1.0):
                raise ValueError(f"{name} must be in [0,1], got {v}")


@dataclass(frozen=True)
class ConfidenceSnapshot:
    """AI's trust in the current recognition: overall + per-field status."""

    overall_confidence: float
    # field name -> validation_status value (str)
    field_status: tuple[tuple[str, str], ...]

    @classmethod
    def from_observation(cls, obs: RawObservation) -> "ConfidenceSnapshot":
        if not isinstance(obs, RawObservation):
            raise TypeError("obs must be a RawObservation")
        statuses = tuple(
            (name, getattr(obs, name).validation_status.value)
            for name in (
                "hero_cards", "board_cards", "street", "pot",
                "stacks", "bet_size", "action",
            )
        )
        return cls(
            overall_confidence=obs.overall_confidence,
            field_status=statuses,
        )


@dataclass(frozen=True)
class RealtimeAnalysis:
    """One frame's analysis output: state + equity + confidence."""

    frame_seq: int
    state: StateSnapshot
    equity: EquitySnapshot
    confidence: ConfidenceSnapshot


__all__ = [
    "StateSnapshot",
    "EquitySnapshot",
    "ConfidenceSnapshot",
    "RealtimeAnalysis",
]
