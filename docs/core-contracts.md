# Core Contracts

Poker Intelligence Engine Phase 0 core domain objects. All objects are
immutable (deep immutability) and JSON-serializable via the serializer
(see `docs/serialization.md`).

> This describes the FROZEN contracts as implemented in Task 1B ~ 1D.

---

## Money

| Object | Semantics |
|---|---|
| `ChipAmount` | Strictly non-negative money value (stack/pot/bet). Backed by `decimal.Decimal`. |
| `ChipDelta` | Signed money change (net_result/profit_loss/chip_change). Backed by `decimal.Decimal`. |

Rules:
- Money is NEVER a `float`.
- `ChipAmount` rejects negative values.
- `ChipDelta` may be negative.
- Arithmetic: `ChipAmount - ChipAmount -> ChipDelta`; `ChipAmount + ChipDelta -> ChipAmount` (raises `InvalidStateError` if result < 0).

---

## Observation layer

| Object | Semantics |
|---|---|
| `ObservationField[T]` | A single recognized value + `confidence` + `source` + `evidence` + `validation_status`. Generic. |
| `RawObservation` | One frame's raw observation of the table. |

Key facts:
- `RawObservation` is **observed data** (from Vision), NOT authoritative state.
- `ObservationField.value` may be `None` when `validation_status == UNKNOWN`.
- `evidence` is deep-frozen (read-only Mapping).

---

## State layer

| Object | Semantics |
|---|---|
| `PlayerState` | One player's state in the current hand. |
| `PokerState` | The system's authoritative, immutable game state. |
| `StateContext` | Read-only context prepared by the Orchestrator for the State Engine. |
| `ValidationResult` | Result of validating a candidate PokerState. |
| `StateEvent` | A single event in the append-only event stream. |

Key facts:
- `RawObservation != PokerState`: observed data vs authoritative state.
- `PokerState` only protects structural correctness; it does NOT infer what happened.
- `PlayerState` stores no `last_action` (that is expressed by `StateEvent`).
- `StateEvent != ActionType`: `ActionType` is the player-action vocabulary; `EventType` (in `StateEvent.event_type`) is the event-stream vocabulary (which also has lifecycle events like `HAND_START` / `DEAL` / `STREET_CHANGE` / `HAND_END`).

---

## Async

| Object | Semantics |
|---|---|
| `RequestContext` | Ties a Slow Path request to a specific hand/state_version. |

Used later for stale-result protection.

---

## Hand

| Object | Semantics |
|---|---|
| `HandSummary` | Settlement summary (final_pot, winners, winnings, net_result). |
| `HandHistory` | Complete append-only record of one hand. |

Rules:
- `winnings`: player_id -> `ChipAmount`.
- `net_result`: player_id -> `ChipDelta`.

---

## Reports

| Object | Semantics |
|---|---|
| `EquityReport` | Equity / pot-odds result. |
| `StrategyReport` | Strategy recommendation from a strategy tier. |
| `ReasoningReport` | Poker Reasoning Layer output. |
| `Decision` | Final decision from the Decision Engine (single exit point). |

Key facts:
- `ReasoningReport` does NOT store a hidden chain-of-thought — only an auditable structured summary.
- `Decision` is the only object produced by the Decision Engine.

---

## Opponent

| Object | Semantics |
|---|---|
| `OpponentProfile` | Aggregate behavioral statistics for a player across hands. |

Frequency fields (`vpip`/`pfr`/`cbet_freq`/`threebet_freq`/`bluff_freq`) are ratios in `[0, 1]`; `af` (aggression factor) is non-negative with no upper bound.

---

## Immutability & time conventions

- All objects use `@dataclass(frozen=True)` + deep immutability (`list -> tuple`, `dict -> MappingProxyType`, `set -> frozenset`).
- All timestamps are timezone-aware `datetime` (naive is rejected).
- All money is `ChipAmount` / `ChipDelta` (never float).
