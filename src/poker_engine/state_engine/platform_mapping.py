"""Explicit visual-slot mapping and conservative candidate-state building.

This module is the platform boundary between stable recognition evidence and
canonical poker state.  A visual ``slot_id`` is never treated as a seat unless
the selected platform/layout contract maps it explicitly.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from types import MappingProxyType
from typing import Mapping

from poker_engine.core.enums import ActionType, PlayerStatus
from poker_engine.core.events import StateEvent
from poker_engine.core.observation import RawObservation, ValidationStatus
from poker_engine.core.state import PokerState, StateContext, ValidationResult
from poker_engine.core.value_objects import ChipAmount

from .action_reconstruction import (
    ActionReconstruction,
    ReconstructionStatus,
    reconstruct_action_event,
)
from .engine import StateEngine, StateTransitionResult


class CandidateMappingStatus(str, Enum):
    """Outcome of mapping one stable observation to an action transition."""

    NO_ACTION = "NO_ACTION"
    EXACT = "EXACT"
    AMBIGUOUS = "AMBIGUOUS"
    INVALID = "INVALID"


def _freeze_slot_map(value: Mapping[int, int], name: str) -> Mapping[int, int]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping")
    normalized: dict[int, int] = {}
    for slot, seat in value.items():
        if not isinstance(slot, int) or isinstance(slot, bool):
            raise TypeError(f"{name} slot keys must be int")
        if not isinstance(seat, int) or isinstance(seat, bool):
            raise TypeError(f"{name} seat values must be int")
        if slot < 0 or seat < 0:
            raise ValueError(f"{name} slots and seats must be >= 0")
        normalized[slot] = seat
    if len(set(normalized.values())) != len(normalized):
        raise ValueError(f"{name} must map one-to-one")
    return MappingProxyType(dict(sorted(normalized.items())))


@dataclass(frozen=True)
class PlatformSeatMapping:
    """Versioned visual geometry to canonical seat contract.

    ``actor_slot_to_seat`` means the recognized actor marker identifies the
    player whose action has just completed.  It does not identify the next
    player to act.
    """

    platform_id: str
    layout_id: str
    version: str
    stack_slot_to_seat: Mapping[int, int]
    action_slot_to_seat: Mapping[int, int]
    actor_slot_to_seat: Mapping[int, int]
    dealer_slot_to_seat: Mapping[int, int]

    def __post_init__(self) -> None:
        for name in ("platform_id", "layout_id", "version"):
            value = getattr(self, name)
            if not isinstance(value, str):
                raise TypeError(f"{name} must be a str")
            if not value:
                raise ValueError(f"{name} must be non-empty")
        for name in (
            "stack_slot_to_seat",
            "action_slot_to_seat",
            "actor_slot_to_seat",
            "dealer_slot_to_seat",
        ):
            object.__setattr__(
                self, name, _freeze_slot_map(getattr(self, name), name)
            )


@dataclass(frozen=True)
class CandidateStateMapping:
    """Auditable mapping result; non-exact results expose no candidate."""

    status: CandidateMappingStatus
    state: PokerState | None = None
    event: StateEvent | None = None
    actor_seat: int | None = None
    observed_action: ActionType | None = None
    reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        reasons = tuple(self.reasons)
        if not all(isinstance(reason, str) and reason for reason in reasons):
            raise TypeError("reasons must contain non-empty strings")
        if self.status is CandidateMappingStatus.EXACT:
            if not isinstance(self.state, PokerState):
                raise ValueError("EXACT requires a candidate state")
            if not isinstance(self.event, StateEvent):
                raise ValueError("EXACT requires an action event")
            if self.actor_seat is None or self.observed_action is None:
                raise ValueError("EXACT requires actor and action")
        elif self.state is not None or self.event is not None:
            raise ValueError("non-EXACT result cannot expose state or event")
        object.__setattr__(self, "reasons", reasons)


def _invalid(reason: str) -> CandidateStateMapping:
    return CandidateStateMapping(CandidateMappingStatus.INVALID, reasons=(reason,))


def _ambiguous(reason: str) -> CandidateStateMapping:
    return CandidateStateMapping(
        CandidateMappingStatus.AMBIGUOUS, reasons=(reason,)
    )


def _valid_value(field):
    if field.validation_status is ValidationStatus.VALID:
        return field.value
    return None


def _resolve_actor_action(
    observation: RawObservation,
    mapping: PlatformSeatMapping,
) -> tuple[int | None, ActionType | None, CandidateStateMapping | None]:
    actor_seats: set[int] = set()
    actor_slot = _valid_value(observation.actor)
    if actor_slot is not None:
        if actor_slot not in mapping.actor_slot_to_seat:
            return None, None, _invalid("unmapped_actor_slot")
        actor_seats.add(mapping.actor_slot_to_seat[actor_slot])

    actions: list[tuple[int | None, ActionType]] = []
    global_action = _valid_value(observation.action)
    if global_action is not None:
        actions.append((None, global_action))
    for slot in observation.slot_actions:
        action = _valid_value(slot.field)
        if action is None:
            continue
        if slot.slot_id not in mapping.action_slot_to_seat:
            return None, None, _invalid("unmapped_action_slot")
        seat = mapping.action_slot_to_seat[slot.slot_id]
        actor_seats.add(seat)
        actions.append((seat, action))

    if not actions:
        return None, None, CandidateStateMapping(
            CandidateMappingStatus.NO_ACTION
        )
    distinct_actions = {action for _, action in actions}
    if len(distinct_actions) != 1:
        return None, None, _ambiguous("conflicting_action_labels")
    if len(actor_seats) != 1:
        reason = "actor_missing" if not actor_seats else "conflicting_actor_slots"
        return None, None, _ambiguous(reason)
    return next(iter(actor_seats)), next(iter(distinct_actions)), None


def _validate_same_decision_frame(
    previous: PokerState, observation: RawObservation
) -> str | None:
    for name, prior in (
        ("hero_cards", previous.hero_cards),
        ("board_cards", previous.board_cards),
        ("street", previous.street),
    ):
        value = _valid_value(getattr(observation, name))
        if value is not None and value != prior:
            return "cards_or_street_changed_during_action"
    return None


def _map_observed_stacks(
    observation: RawObservation,
    mapping: PlatformSeatMapping,
) -> tuple[dict[int, ChipAmount], str | None]:
    by_seat: dict[int, ChipAmount] = {}
    for slot in observation.slot_stacks:
        value = _valid_value(slot.field)
        if value is None:
            continue
        if slot.slot_id not in mapping.stack_slot_to_seat:
            return {}, "unmapped_stack_slot"
        seat = mapping.stack_slot_to_seat[slot.slot_id]
        if seat in by_seat and by_seat[seat] != value:
            return {}, "conflicting_stack_values"
        by_seat[seat] = value
    return by_seat, None


def map_action_candidate(
    previous: PokerState,
    observation: RawObservation,
    mapping: PlatformSeatMapping,
) -> CandidateStateMapping:
    """Build and validate one canonical action transition, or fail closed."""
    if not isinstance(previous, PokerState):
        raise TypeError("previous must be a PokerState")
    if not isinstance(observation, RawObservation):
        raise TypeError("observation must be a RawObservation")
    if not isinstance(mapping, PlatformSeatMapping):
        raise TypeError("mapping must be a PlatformSeatMapping")

    actor_seat, action, resolved = _resolve_actor_action(observation, mapping)
    if resolved is not None:
        return resolved
    assert actor_seat is not None and action is not None
    players = {player.seat: player for player in previous.players}
    if actor_seat not in players:
        return _invalid("mapped_actor_seat_not_in_state")

    frame_error = _validate_same_decision_frame(previous, observation)
    if frame_error:
        return _invalid(frame_error)

    dealer_slot = _valid_value(observation.dealer_pos)
    if dealer_slot is not None:
        if dealer_slot not in mapping.dealer_slot_to_seat:
            return _invalid("unmapped_dealer_slot")
        dealer_seat = mapping.dealer_slot_to_seat[dealer_slot]
        canonical_dealers = {
            player.seat for player in previous.players if player.is_dealer
        }
        if canonical_dealers != {dealer_seat}:
            return _invalid("dealer_mapping_conflicts_with_state")

    observed_stacks, stack_error = _map_observed_stacks(observation, mapping)
    if stack_error:
        return _invalid(stack_error)
    unknown_seats = set(observed_stacks) - set(players)
    if unknown_seats:
        return _invalid("mapped_stack_seat_not_in_state")
    changed_seats = {
        seat for seat, value in observed_stacks.items()
        if value != players[seat].stack
    }
    if changed_seats - {actor_seat}:
        return _invalid("multiple_players_changed")

    before_actor = players[actor_seat]
    after_stack = observed_stacks.get(actor_seat, before_actor.stack)
    spent = before_actor.stack.value - after_stack.value
    if spent < 0:
        return _invalid("stack_increase_during_action")
    if action in {ActionType.BET, ActionType.RAISE, ActionType.CALL,
                  ActionType.ALL_IN} and actor_seat not in observed_stacks:
        return _invalid("actor_stack_missing_for_chip_action")
    if action in {ActionType.FOLD, ActionType.CHECK} and spent != 0:
        return _invalid("non_chip_action_changed_stack")

    pot_value = _valid_value(observation.pot)
    if spent > 0 and pot_value is None:
        return _invalid("pot_missing_for_chip_action")
    next_pot = pot_value if pot_value is not None else previous.pot

    status = before_actor.status
    has_cards = before_actor.has_cards
    if action is ActionType.FOLD:
        status = PlayerStatus.FOLDED
        has_cards = False
    elif after_stack.value == 0:
        status = PlayerStatus.ALL_IN

    after_actor = replace(
        before_actor,
        stack=after_stack,
        committed_this_street=ChipAmount(
            before_actor.committed_this_street.value + spent
        ),
        committed_this_hand=ChipAmount(
            before_actor.committed_this_hand.value + spent
        ),
        status=status,
        has_cards=has_cards,
    )
    next_players = tuple(
        after_actor if player.seat == actor_seat else player
        for player in previous.players
    )
    candidate = PokerState(
        state_version=previous.state_version + 1,
        hand_id=previous.hand_id,
        street=previous.street,
        hero_cards=previous.hero_cards,
        board_cards=previous.board_cards,
        players=next_players,
        pot=next_pot,
        current_bet=ChipAmount(max(
            previous.current_bet.value,
            after_actor.committed_this_street.value,
        )),
        to_call=previous.to_call,
        actor=previous.actor,
    )
    reconstruction: ActionReconstruction = reconstruct_action_event(
        previous,
        candidate,
        actor_seat=actor_seat,
        observed_action=action,
        timestamp=observation.timestamp,
        source=(
            f"platform_mapping:{mapping.platform_id}:"
            f"{mapping.layout_id}:{mapping.version}"
        ),
    )
    if reconstruction.status is ReconstructionStatus.AMBIGUOUS:
        return CandidateStateMapping(
            CandidateMappingStatus.AMBIGUOUS,
            actor_seat=actor_seat,
            observed_action=action,
            reasons=reconstruction.reasons,
        )
    if reconstruction.status is ReconstructionStatus.INVALID:
        return CandidateStateMapping(
            CandidateMappingStatus.INVALID,
            actor_seat=actor_seat,
            observed_action=action,
            reasons=reconstruction.reasons,
        )
    return CandidateStateMapping(
        CandidateMappingStatus.EXACT,
        state=candidate,
        event=reconstruction.event,
        actor_seat=actor_seat,
        observed_action=action,
    )


class PlatformMappedStateEngine(StateEngine):
    """StateEngine extension enabled only with an explicit platform mapping."""

    def __init__(self, mapping: PlatformSeatMapping) -> None:
        if not isinstance(mapping, PlatformSeatMapping):
            raise TypeError("mapping must be a PlatformSeatMapping")
        self._mapping = mapping

    def transition(
        self,
        previous_state: PokerState,
        observation: RawObservation,
        context: StateContext,
    ) -> StateTransitionResult:
        if not isinstance(context, StateContext):
            raise TypeError("context must be a StateContext")
        if context.previous_state is not None and (
            context.previous_state != previous_state
        ):
            return super().transition(previous_state, observation, context)
        mapped = map_action_candidate(previous_state, observation, self._mapping)
        if mapped.status is CandidateMappingStatus.NO_ACTION:
            return super().transition(previous_state, observation, context)
        if mapped.status is not CandidateMappingStatus.EXACT:
            return StateTransitionResult(
                state=previous_state,
                events=(),
                validation=ValidationResult(
                    is_valid=False, errors=mapped.reasons, warnings=()
                ),
                changed=False,
            )
        assert mapped.state is not None and mapped.event is not None
        return StateTransitionResult(
            state=mapped.state,
            events=(mapped.event,),
            validation=ValidationResult(is_valid=True),
            changed=True,
        )


__all__ = [
    "CandidateMappingStatus",
    "CandidateStateMapping",
    "PlatformMappedStateEngine",
    "PlatformSeatMapping",
    "map_action_candidate",
]
