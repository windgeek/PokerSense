"""State change detection for the realtime pipeline.

Compares two consecutive ``RawObservation`` values and reports which fields
changed *materially*. Only a material change should trigger a downstream
StateEngine transition + analysis refresh — at 30 FPS the underlying poker
state changes far more rarely than frames arrive, so this is the event-driven
gate that keeps the pipeline cheap.

Change rule per field: a field is "changed" when BOTH the previous and the
current observation carry a VALID, non-None value for it AND those values
differ. A field that is UNKNOWN/CONFLICT (or None) is not a change signal.
"""

from __future__ import annotations

from dataclasses import dataclass

from poker_engine.core.observation import RawObservation, ValidationStatus

# Fields whose material change we track (matches Task 8 output boundary).
_TRACKED = (
    "hero_cards",
    "board_cards",
    "street",
    "pot",
    "stacks",
    "bet_size",
    "action",
)


@dataclass(frozen=True)
class ChangeReport:
    changed: bool
    changed_fields: tuple[str, ...]


def _field_value(obs: RawObservation, name: str):
    field = getattr(obs, name)
    if field.validation_status is not ValidationStatus.VALID:
        return None
    return field.value


def detect_change(previous: RawObservation, current: RawObservation) -> ChangeReport:
    """Return which tracked fields materially changed between two observations."""
    if not isinstance(previous, RawObservation):
        raise TypeError("previous must be a RawObservation")
    if not isinstance(current, RawObservation):
        raise TypeError("current must be a RawObservation")

    changed_fields: list[str] = []
    for name in _TRACKED:
        prev_val = _field_value(previous, name)
        curr_val = _field_value(current, name)
        if prev_val is None or curr_val is None:
            # a field that is not confidently known on either side is not a
            # deterministic "change" signal we can act on.
            continue
        if prev_val != curr_val:
            changed_fields.append(name)

    return ChangeReport(
        changed=bool(changed_fields),
        changed_fields=tuple(changed_fields),
    )


__all__ = ["ChangeReport", "detect_change"]
