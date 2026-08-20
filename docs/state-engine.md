# State Engine

Pure, deterministic state reconciliation layer.

## 职责

将 `Previous PokerState + RawObservation + StateContext` 转换为 `StateTransitionResult`
（canonical state + events + validation）。

一句话：Vision 说「我看到了什么」（RawObservation），State Engine 决定「系统现在该认定
什么」（Canonical PokerState）。

## 不负责

- 完整德州扑克规则裁判（side pot / minimum raise / showdown winner / hand evaluator …）
- Confidence Gate（不读置信度数值、不设阈值）
- hand boundary 检测、bootstrap（不凭空创建 PokerState）
- Hand Memory（State Engine 不 import HandMemory）

---

## PURE 约束

State Engine 是纯函数：禁止 datetime.now / random / uuid / DB / 全局 mutable state。
事件 timestamp 用 observation.timestamp，source = "state_engine"。

## API

```python
@dataclass(frozen=True)
class StateTransitionResult:
    state: PokerState          # material change -> new; else previous (永不 None)
    events: tuple[StateEvent, ...]
    validation: ValidationResult
    changed: bool

class StateEngine:
    def transition(previous_state, observation, context) -> StateTransitionResult
```

## Canonical merge policy

「有可靠新信息才覆盖，否则保留 previous」。

| observation status | 行为 |
|---|---|
| VALID（value 非 None） | 覆盖候选 |
| UNKNOWN / value None | 保留 previous |
| LOW_CONFIDENCE | 保留 previous + warning |
| CONFLICT | 保留 previous + warning |

## 当前允许 / 不允许的更新（Task 3 v1）

| 字段 | 规则 |
|---|---|
| hero_cards ✅ | VALID 更新；2→0 regression → invalid |
| board_cards ✅ | VALID 更新；count 减少 → invalid（整次 transition invalid） |
| street ✅ | VALID 更新；倒退 → invalid；前进 → STREET_CHANGE 事件 |
| pot ✅ | VALID 更新；下降 → 保留 + warning（不 overflow） |
| actor ⏸ | 不更新（int 语义未定义，不猜） |
| dealer_pos ⏸ | 不更新 |
| stacks ⏸ | 不更新 PlayerState.stack |
| bet_size ⏸ | 不计算 committed/current_bet/to_call |
| players ⏸ | 保持 previous |
| action ⏸ | 不生成需绑定玩家的 FOLD/CALL/BET/RAISE/ALL_IN 事件 |

## Event

- 仅 STREET_CHANGE 与 DEAL。
- 固定顺序：STREET_CHANGE → DEAL。
- event.state_version = new_state.state_version。
- event.timestamp = observation.timestamp；source = "state_engine"。

## version policy

- material change → previous.state_version + 1
- no-op / invalid → 不推进

## ValidationResult

复用 Core `ValidationResult`。`is_valid=False` 表示 transition 不可接受（board/hero/street
regression），此时 state 保持 previous、events=()、changed=False。

## 异常分工

- Programmer error（参数类型错、context.previous_state 与参数不一致）→ 上抛
  `StateEngineError` / `TypeError`。
- Domain conflict（regression / Core invariant 构造失败）→ `ValidationResult(is_valid=False)`，
  仅捕获 `(InvalidStateError, ValueError, TypeError)`，禁止 broad except。

## 非目标（non-goals）

side pot、bet 合法性、minimum raise、heads-up 特例、tournament、rake、split pot、
showdown winner、hand evaluator、GTO、bet sizing、hand boundary、筹码守恒。
