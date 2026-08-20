"""Scripted demo analysis sequence (no real Vision/Capture involved).

Used until a real, calibrated ``RealtimePipeline`` (real capture + vision
against an actual poker client) exists -- see the project roadmap. This
lets the desktop shell and its wire contract be built and exercised end to
end today, without pretending any of it is real recognition.

Mirrors ``ui/app.js``'s ``DEMO_SEQUENCE`` (same hand, same numbers) so the
JS-only preview and the real server-driven demo look identical.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from poker_engine.core.enums import Rank, Street, Suit
from poker_engine.core.value_objects import Card, ChipAmount
from poker_engine.realtime.analysis import (
    ConfidenceSnapshot,
    EquitySnapshot,
    RealtimeAnalysis,
    StateSnapshot,
)


def _card(code: str) -> Card:
    rank = Rank(code[0])
    suit = Suit(code[1])
    return Card(rank, suit)


def _cards(*codes: str) -> tuple[Card, ...]:
    return tuple(_card(c) for c in codes)


_FIELDS = ("hero_cards", "board_cards", "street", "pot", "stacks", "bet_size", "action")


def _confidence(overall: float, **overrides: str) -> ConfidenceSnapshot:
    statuses = tuple((f, overrides.get(f, "valid")) for f in _FIELDS)
    return ConfidenceSnapshot(overall_confidence=overall, field_status=statuses)


DEMO_SEQUENCE: tuple[RealtimeAnalysis, ...] = (
    RealtimeAnalysis(
        frame_seq=1,
        state=StateSnapshot(
            street=Street.PREFLOP,
            hero_cards=_cards("Ah", "Kh"),
            board_cards=(),
            pot=ChipAmount("1.5"),
        ),
        equity=EquitySnapshot(win_rate=0.64, tie_rate=0.02),
        confidence=_confidence(0.98),
    ),
    RealtimeAnalysis(
        frame_seq=2,
        state=StateSnapshot(
            street=Street.FLOP,
            hero_cards=_cards("Ah", "Kh"),
            board_cards=_cards("Qh", "9h", "2c"),
            pot=ChipAmount("6"),
        ),
        equity=EquitySnapshot(win_rate=0.71, tie_rate=0.01),
        confidence=_confidence(0.95, bet_size="low_confidence"),
    ),
    RealtimeAnalysis(
        frame_seq=3,
        state=StateSnapshot(
            street=Street.TURN,
            hero_cards=_cards("Ah", "Kh"),
            board_cards=_cards("Qh", "9h", "2c", "5h"),
            pot=ChipAmount("18"),
        ),
        equity=EquitySnapshot(win_rate=0.86, tie_rate=0.01),
        confidence=_confidence(0.97),
    ),
    RealtimeAnalysis(
        frame_seq=4,
        state=StateSnapshot(
            street=Street.RIVER,
            hero_cards=_cards("Ah", "Kh"),
            board_cards=_cards("Qh", "9h", "2c", "5h", "7s"),
            pot=ChipAmount("42"),
        ),
        equity=EquitySnapshot(win_rate=0.91, tie_rate=0.0),
        confidence=_confidence(0.6, board_cards="conflict", stacks="unknown"),
    ),
)


async def demo_analysis_stream(
    interval_seconds: float = 3.2,
) -> AsyncIterator[RealtimeAnalysis]:
    """Yield the demo hand forever, looping, one step every ``interval_seconds``."""
    i = 0
    while True:
        yield DEMO_SEQUENCE[i % len(DEMO_SEQUENCE)]
        i += 1
        await asyncio.sleep(interval_seconds)


__all__ = ["DEMO_SEQUENCE", "demo_analysis_stream"]
