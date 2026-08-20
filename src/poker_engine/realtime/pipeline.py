"""Realtime pipeline: the event-driven loop that ties the layers together.

    FrameSource -> VisionEngine(process) -> RawObservation
        -> ChangeDetector -> (material change?) -> ApplicationOrchestrator
        -> StateEngine -> state snapshot + equity + confidence

This layer OWNS only the frame lifecycle and the change gating. It does not:
  - auto-operate the table / place bets (out of scope),
  - produce strategy recommendations (later tasks),
  - construct Vision/State components (they are injected).

Every step is deterministic given the injected components and frame source.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from poker_engine.core.observation import RawObservation, ValidationStatus
from poker_engine.core.state import PokerState
from poker_engine.orchestrator import ApplicationOrchestrator
from poker_engine.perceptual.capture.base import Frame
from poker_engine.perceptual.vision.engine import VisionEngine
from poker_engine.perceptual.vision.table_map import TableMap

from .analysis import (
    ConfidenceSnapshot,
    EquitySnapshot,
    RealtimeAnalysis,
    StateSnapshot,
)
from .change_detector import ChangeReport, detect_change
from .equity import EquityStrategy, MonteCarloRandomRangeEquity
from .frame_source import FrameSource


@dataclass(frozen=True)
class PipelineStep:
    """Result of processing one frame.

    ``analysis_changed`` is True only when this step produced a *new* canonical
    state + equity snapshot. Every step still carries its own recognition
    confidence so a client never renders stale table data after an abstention.
    """

    frame_seq: int
    analysis: RealtimeAnalysis
    change: ChangeReport
    analysis_changed: bool


class RealtimePipeline:
    """Event-driven realtime analysis driver."""

    def __init__(
        self,
        frame_source: FrameSource,
        vision: VisionEngine,
        table_map: TableMap,
        orchestrator: ApplicationOrchestrator,
        equity_strategy: EquityStrategy | None = None,
        equity_trials: int = 2000,
        equity_seed: int = 0,
        hero_confirmation_frames: int = 1,
    ) -> None:
        if not isinstance(vision, VisionEngine):
            raise TypeError("vision must be a VisionEngine")
        if not isinstance(table_map, TableMap):
            raise TypeError("table_map must be a TableMap")
        if not isinstance(orchestrator, ApplicationOrchestrator):
            raise TypeError("orchestrator must be an ApplicationOrchestrator")
        self._frame_source = frame_source
        self._vision = vision
        self._table_map = table_map
        self._orchestrator = orchestrator
        if equity_strategy is None:
            equity_strategy = MonteCarloRandomRangeEquity(
                trials=equity_trials, seed=equity_seed
            )
        self._equity_strategy = equity_strategy
        if isinstance(hero_confirmation_frames, bool) or not isinstance(
            hero_confirmation_frames, int
        ):
            raise TypeError("hero_confirmation_frames must be an int")
        if hero_confirmation_frames < 1:
            raise ValueError("hero_confirmation_frames must be >= 1")
        self._hero_confirmation_frames = hero_confirmation_frames
        self._pending_hero_cards = None
        self._pending_hero_count = 0

        self._previous_obs: RawObservation | None = None
        self._current_analysis: RealtimeAnalysis | None = None

    def step(self) -> PipelineStep | None:
        """Advance one frame. Returns None when the frame source is exhausted."""
        frame = self._frame_source.next_frame()
        if frame is None:
            return None

        raw_obs = self._vision.process(frame, self._table_map)
        obs = self._confirmed_hero_observation(raw_obs)

        if self._previous_obs is None:
            # First frame: no previous to diff against; still record the
            # opening state through the orchestrator.
            self._advance(obs, frame)
            change = ChangeReport(changed=True, changed_fields=())
            self._previous_obs = obs
            assert self._current_analysis is not None
            return PipelineStep(
                frame_seq=frame.frame_seq,
                analysis=self._current_analysis,
                change=change,
                analysis_changed=True,
            )

        change = detect_change(self._previous_obs, obs)
        if change.changed:
            self._advance(obs, frame)

        self._previous_obs = obs
        assert self._current_analysis is not None
        # The state snapshot is intentionally retained between material
        # transitions, but presentation confidence is per-frame.  Returning
        # the old confidence here made the UI show stale cards indefinitely
        # after the live recognizer had already abstained.
        fresh_analysis = replace(
            self._current_analysis,
            frame_seq=frame.frame_seq,
            confidence=ConfidenceSnapshot.from_observation(obs),
        )
        return PipelineStep(
            frame_seq=frame.frame_seq,
            analysis=fresh_analysis,
            change=change,
            analysis_changed=change.changed,
        )

    def _confirmed_hero_observation(self, obs: RawObservation) -> RawObservation:
        """Require consecutive identical hero reads before accepting a hand.

        A single frame can be captured during a deal animation or while a
        browser surface is changing.  It must never seed the immutable hero
        cards in the state engine.  Until the configured number of matching
        reads arrives, expose the field as UNKNOWN to both state and UI.
        """
        hero = obs.hero_cards
        cards = hero.value
        if (
            hero.validation_status is ValidationStatus.VALID
            and cards is not None
            and len(cards) == 2
        ):
            if cards == self._pending_hero_cards:
                self._pending_hero_count += 1
            else:
                self._pending_hero_cards = cards
                self._pending_hero_count = 1
            if self._pending_hero_count >= self._hero_confirmation_frames:
                return obs
        else:
            self._pending_hero_cards = None
            self._pending_hero_count = 0

        return replace(
            obs,
            hero_cards=replace(
                hero,
                value=(),
                confidence=0.0,
                validation_status=ValidationStatus.UNKNOWN,
            ),
        )

    def _advance(self, obs: RawObservation, frame: Frame) -> None:
        self._orchestrator.process_observation(obs)
        state = self._latest_state()
        snapshot = RealtimeAnalysis(
            frame_seq=frame.frame_seq,
            state=StateSnapshot.from_state(state),
            equity=self._compute_equity(state),
            confidence=ConfidenceSnapshot.from_observation(obs),
        )
        self._current_analysis = snapshot

    def _latest_state(self) -> PokerState:
        active = self._orchestrator._hand_memory.active_hand_id
        if active is None:
            raise RuntimeError("no active hand; call start_hand before stepping")
        state = self._orchestrator._hand_memory.latest_state(active)
        if state is None:
            raise RuntimeError("active hand has no state")
        return state

    def _compute_equity(self, state: PokerState) -> EquitySnapshot:
        """Delegate equity to the injected strategy."""
        return self._equity_strategy.compute(state)

    def latest_analysis(self) -> RealtimeAnalysis | None:
        return self._current_analysis


__all__ = ["RealtimePipeline", "PipelineStep"]
