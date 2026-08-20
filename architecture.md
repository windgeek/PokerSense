# Poker Intelligence Engine — 架构设计文档 v0.2.1

> 单桌德州扑克 AI 分析系统 · 感知→状态→推理→策略输出
> 最高设计原则：**正确性 > 稳定性 > 可观测性 > 性能 > 功能数量**
> **状态：FROZEN（架构已冻结，除非评审后明确决定重构，否则不再变更。）**

## 修订记录

| 版本 | 变更 |
|---|---|
| v0.2.1 | 契约层修订：① Core Domain 深层不可变（immutable container）② 金额统一值对象（decimal，禁用 float），`ChipAmount`（严格非负）+ `ChipDelta`（可正负）③ Slow Path stale result protection（`RequestContext`）④ 删除 `ReasoningReport.reasoning_chain`，改为可审计结构化摘要 ⑤ 正式定义 `PlayerState` ⑥ Orchestrator 措辞修正为"中央编排器/唯一调度入口" ⑦ Task 4 验收改为"所有 Phase 0 规定场景全部通过" |

---

## 目录

1. [总体架构 v0.2](#1-总体架构-v02)
2. [v0.1 → v0.2 Change Log](#2-v01--v02-change-log)
3. [项目目录结构](#3-项目目录结构)
4. [端到端数据流图（Fast Path + Slow Path）](#4-端到端数据流图fast-path--slow-path)
5. [核心数据契约](#5-核心数据契约)
6. [Phase 0 ~ Phase 3 开发计划](#6-phase-0--phase-3-开发计划)
7. [实现任务清单 v0.2](#7-实现任务清单-v02)
8. [附录：技术选型与风险](#8-附录技术选型与风险)

---

# 1. 总体架构 v0.2

## 1.1 设计原则（继承 v0.1 + 强化）

- **P1 感知与推理解耦**：Vision 管"看"，State 管"算"，Strategy/Reasoning 管"想"。
- **P2 一切皆纯数据流**：模块间只传不可变结构化对象，禁止跨模块 import 内部实现。
- **P3 可观测、可回放**：每帧输入、每步决策都落盘；能回放 = 能调试 = 能回归。
- **P4 State Engine 纯净**（v0.2 新增）：State Engine 是纯函数，不访问 DB/Repository/Solver/Vision。
- **P5 Confidence Gate**（v0.2 新增）：关键字段置信度不足即阻断，宁可 UNKNOWN，不产出错误决策。
- **P6 Fast/Slow 分离**（v0.2 新增）：缓存/DB 走快路径，Solver/LLM 走慢路径，二者解耦。

## 1.2 新增 / 变更的模块

v0.2 在 v0.1 基础上增加三个关键角色：

| 模块 | 状态 | 说明 |
|---|---|---|
| **Application Orchestrator** | 新增 | 中央编排器 / 唯一调度入口，协调所有模块，不实现任何算法 |
| **Strategy Engine** | 新增 | 包裹 Solver Adapter，缓存/DB/预计算/Solver 四级降级 |
| **Poker Reasoning Layer** | 拆分 | LLM/PokerSkill 从 Decision Engine 中剥离为独立 Adapter 层 |

并对三个既有模块做了修正：

| 模块 | 修正 |
|---|---|
| **State Engine** | 明确不依赖 Hand Memory，输入改为 `RawObservation + PreviousState + StateContext` |
| **Decision Engine** | 不再直接持有 LLM，只消费统一的 `ReasoningReport` |
| **Solver Adapter** | 降级为 Strategy Engine 的最后一级来源 |

## 1.3 分层与依赖

```
 APPLICATION LAYER
   ├── UI（纯消费者）
   └── Application Orchestrator（调度，无算法）

 REASONING LAYER（未实现）
   ├── Decision Engine（融合出口）
   ├── Strategy Engine（策略来源管理）
   │     └── Solver Adapter（TexasSolver / Mock）
   ├── Poker Reasoning Layer（LLM / PokerSkill Adapter）
   ├── Opponent Model（对手画像）
   └── Equity Engine（赢率/赔率）── 已实现（枚举 + 蒙特卡洛 + pot odds + 范围）

 REALTIME LAYER（已实现，2026-08 接手时补录进本文档）
   ├── FrameSource（Synthetic / 真实 CaptureService 注入）
   ├── ChangeDetector（状态有效变化检测，避免每帧都跑 State/Equity）
   └── RealtimePipeline（驱动循环：Capture → Vision → ChangeDetector → Orchestrator → Equity）

 DOMAIN LAYER（已实现）
   ├── State Engine（纯函数）
   └── Hand Memory（事件溯源 / 查询 / 回放）

 PERCEPTION LAYER（已实现）
   ├── Vision Engine（带置信度证据）
   └── Capture Service（FakeBackend / MssBackend[Windows] / QuartzBackend[macOS]）
```

**依赖铁律**：严格单向向下。Orchestrator 是所有模块的调用方；State 与 Hand Memory 之间无直接依赖（由 Orchestrator 负责联动）；Decision Engine 是唯一对外产出 `Decision` 的出口；Realtime 层位于 Orchestrator 之上，驱动整条链路但不实现任何算法。

> 本图 2026-08 接手时核对过一次代码：v0.2.1 原文没有 Realtime Layer（Task 8 是后补的），Vision/Capture
> 子模块的真实文件名也和 §3 目录结构不完全一致（见 §3 开头的说明）。已在此处同步，§3 保留原始规划
> 供历史参照，不代表当前真实文件布局。

---

# 2. v0.1 → v0.2 Change Log

| # | 变更 | 改了什么 | 为什么改 | 影响模块 |
|---|---|---|---|---|
| 1 | **Python 固定 3.11.x** | 技术选型从"3.11+/建议 3.12"收紧为"3.11.x" | 兼容 OpenCV/OCR/ONNX/PyTorch/TexasSolver/较老 Poker 库，优先稳定性 | pyproject、开发环境、初始化任务 |
| 2 | **State Engine 纯净化** | 移除 State Engine 对 Hand Memory 的依赖；输入改为 `RawObservation + PreviousState + StateContext`，输出增加 `StateEvents + ValidationResult` | 消除纯函数定义与 DB 依赖的矛盾，提升可测性 | State Engine、Hand Memory、Orchestrator |
| 3 | **Poker Reasoning Layer 独立** | LLM/PokerSkill 从 Decision Engine 剥离为 `reasoning/llm/` 适配层 | 让 Decision Engine 与具体 LLM 解耦，换模型不影响下游 | Decision Engine、新增 reasoning/llm/ |
| 4 | **新增 Strategy Engine** | Solver Adapter 之上加缓存/DB/预计算层级 | 实时系统不能每次跑 Solver；长线目标 ≤500ms | Solver、Strategy Engine、Decision |
| 5 | **Vision 验收标准重定** | 拆分为逐字段阈值（Hero/Board≥99.5% 等）+ Confidence Gate | 单一 ≥95% 无法保证下游正确性 | Vision Engine、State Engine、契约层 |
| 6 | **新增 Orchestrator** | 引入调度器统一管理数据流/生命周期/超时/降级 | 明确编排职责，避免 God Object 与模块乱耦合 | 全局 |

---

# 3. 项目目录结构

> 以下是 v0.2 时期的原始规划，保留作历史参照。**实际文件布局已经分叉**（例如 Vision 子模块的真实
> 文件名是 `card_recognizer.py`/`amount_recognizer.py`/`board_slot_detector.py` 等，不是这里写的
> `card_detect.py`/`text_ocr.py`；`memory/` 实际只有 `hand_memory.py` + `errors.py`，没有拆分成
> `event_store.py`/`hand_history.py`/`repository.py`/`replay.py`；`strategy/`/`opponent/`/
> `reasoning/`/`ui/`/`infra/` 均未创建）。要看当前真实结构，直接看仓库 `src/poker_engine/` 或
> `README.md` 的模块总览表。

```
poker-intelligence-engine/
├── README.md
├── pyproject.toml               # requires-python = ">=3.11,<3.12"
├── Makefile
├── .pre-commit-config.yaml
├── .python-version              # 3.11.x
├── docs/
│   ├── architecture.md          # 本文档
│   ├── adr/                     # ADR 决策记录
│   └── data-contracts/          # 数据契约 schema
├── configs/
│   ├── default.yaml
│   ├── platform/                # 不同平台 Table Mapping
│   └── thresholds.yaml          # Confidence Gate 阈值配置
├── src/poker_engine/
│   ├── __init__.py
│   ├── core/                    # 领域层（零第三方依赖）
│   │   ├── state.py             #   PokerState / StateContext / ValidationResult
│   │   ├── events.py            #   StateEvent / FrameEvent
│   │   ├── observation.py       #   RawObservation / ObservationField<T>
│   │   ├── hand.py              #   HandHistory
│   │   ├── action.py            #   Action / Bet / Street
│   │   ├── value_objects.py     #   ChipAmount (decimal) / Card / Position 等值对象
│   │   ├── reports.py           #   EquityReport / StrategyReport / ReasoningReport / Decision
│   │   ├── opponents.py         #   OpponentProfile / PlayerState
│   │   ├── request_context.py   #   RequestContext（异步元数据 / stale protection）
│   │   └── errors.py
│   │
│   ├── orchestrator/
│   │   ├── app.py               #   Application Orchestrator
│   │   ├── context_builder.py   #   StateContext 准备
│   │   ├── pipeline.py          #   Fast/Slow path 调度
│   │   └── lifecycle.py         #   生命周期/超时/降级
│   │
│   ├── perceptual/
│   │   ├── capture/
│   │   │   ├── base.py
│   │   │   └── mss_backend.py
│   │   └── vision/
│   │       ├── engine.py
│   │       ├── table_map.py
│   │       ├── card_detect.py
│   │       ├── text_ocr.py
│   │       ├── confidence_gate.py
│   │       └── models/
│   │
│   ├── memory/                  # Hand Memory
│   │   ├── event_store.py
│   │   ├── hand_history.py
│   │   ├── repository.py
│   │   └── replay.py
│   │
│   ├── equity/
│   │   ├── calculator.py
│   │   ├── montecarlo.py
│   │   ├── enumeration.py
│   │   ├── pot_odds.py
│   │   └── ranges.py
│   │
│   ├── strategy/                # Strategy Engine（新增）
│   │   ├── engine.py
│   │   ├── cache.py
│   │   ├── preflop_db.py
│   │   ├── precomputed.py
│   │   └── solver/
│   │       ├── base.py          #   SolverBase
│   │       ├── texas_solver.py
│   │       ├── mock.py
│   │       └── registry.py
│   │
│   ├── opponent/
│   │   ├── profile.py
│   │   ├── tracker.py
│   │   └── estimator.py
│   │
│   ├── reasoning/
│   │   ├── decision_engine.py
│   │   ├── fusion.py
│   │   ├── rules.py
│   │   ├── complexity_detector.py
│   │   └── llm/
│   │       ├── base.py
│   │       ├── poker_skill_adapter.py
│   │       ├── mock_adapter.py
│   │       └── registry.py
│   │
│   ├── ui/
│   │   ├── app.py
│   │   ├── overlay.py
│   │   └── components/
│   │
│   └── infra/
│       ├── config.py
│       ├── logging.py
│       └── telemetry.py
│
└── tests/
    ├── unit/
    ├── integration/
    ├── fixtures/                # 假数据剧本（Phase 0 用）
    └── golden/                  # 黄金样本
```

---

# 4. 端到端数据流图（Fast Path + Slow Path）

## 4.1 主链路（经 Orchestrator 调度）

```
        Capture ──Frame──> Vision ──RawObservation──> State Engine ──NewState──> Hand Memory
                                                                  │
                                                                  ├──> Equity Engine
                                                                  │
                                                                  └──> Strategy Engine
                                                                            │
                                                                            └──> Decision Engine ──Decision──> UI
```

## 4.2 Fast Path（≤500ms，关键路径）

```
Screen → Vision → State → Equity → Strategy(Cache/DB) → Decision → UI
```

- 只走缓存命中 / Preflop DB / 预计算，**不调用 Solver，不调用 LLM**。
- Confidence Gate 全部通过才进入。
- LLM 与 Solver 完全不在本路径。

## 4.3 Slow Path（1~3s，高级分析，异步）

```
复杂牌局 ──触发──> Solver Adapter / Poker Reasoning
                        │
                        └──> Decision Update（异步覆盖 Fast 结果）
```

- 由 `complexity_detector` 判定是否需要 Slow Path。
- Slow 结果返回后**更新**已有 Decision，不阻塞 Fast Path 首次输出。

## 4.4 时序示意

```
 t=0       t=100ms     t=300ms   t=500ms          t=1~3s
 截图 ──► 感知 ──► 状态 ──► Equity/缓存 ──► Fast Decision ──► [UI 首次展示]
                                                      │
                                              (异步) Solver / LLM ──► Decision Update
```

---

# 5. 核心数据契约

> 通用可观测字段约定：`value / confidence / timestamp / source / evidence` 作为关键数据的公共基础。

## 5.0 不可变性与数值铁律（v0.2.1 新增，最高优先级）

1. **深层不可变（Deep Immutability）**：所有 Core Object 不仅 `frozen=True`，内部容器也必须不可变。
   - `list` → `tuple`
   - `set` → `frozenset`
   - `dict` → `MappingProxyType` 只读映射（构造时先 defensive copy 再只读暴露）
   - 任何 `payload` / `evidence` / 集合字段，**调用方不得原地修改（in-place mutate）**；违反即破坏 Event Sourcing 与不可变状态原则。
   - 约束：`events: tuple[StateEvent, ...]`、`board_cards: tuple[Card, ...]`、`players: tuple[PlayerState, ...]`；嵌套对象本身也必须是不可变的。
   - 若确实需要 mapping：构造时 `defensive copy`，对外暴露 read-only interface（`MappingProxyType`）。
2. **金额禁用 float**：所有筹码/金额字段统一使用值对象（底层 `decimal.Decimal`），禁止以 `float` 表示筹码（详见 §5.13）。存量/底池/下注等用**严格非负** `ChipAmount`；净结果/盈亏/变化量用**可正负** `ChipDelta`。

## 5.1 Frame
- `image`：原始帧像素（或引用）
- `timestamp`：采集时间
- `window_id / window_rect`：来源窗口与坐标
- `frame_seq`：单调递增帧号

## 5.2 ObservationField<T>（泛型字段）
- `value: T | None`：识别值
- `confidence: float`：0~1（置信度本身是概率，可用 float）
- `source: str`：识别来源（ocr/detect/model/template）
- `evidence: Mapping[str, Any]`：原始证据（只读映射，如 ROI 引用、候选列表、坐标框）
- `timestamp`：识别时间
- `validation_status`：`VALID / LOW_CONFIDENCE / UNKNOWN / CONFLICT`

## 5.3 RawObservation
- `frame_seq`：关联帧
- 一堆 `ObservationField<T>`：`hero_cards` / `board_cards` / `pot` / `stacks` / `bet_size` / `action` / `street` / `dealer_pos` / `actor`
- `overall_confidence`：综合置信度

## 5.4 PokerState（不可变权威状态）
- `state_version`：单调递增版本号
- `street`：preflop / flop / turn / river / showdown
- `hero_cards / board_cards`：`tuple[Card, ...]`
- `players: tuple[PlayerState, ...]`（见 §5.13）
- `pot / current_bet / to_call`：均为 `ChipAmount`
- `actor`：当前行动方
- `hand_id`：所属手牌
- 深层不可变（deep immutability）

## 5.5 StateContext（由 Orchestrator 准备）
- 上一个稳定状态的引用或关键摘要
- 平台规则（盲注结构、下注上限，金额用 `ChipAmount`）
- 阈值配置（Confidence Gate）
- 已累计的事件尾部（供去重/补全，只读）

## 5.6 StateEvent
- `event_type`：DEAL / BET / RAISE / CALL / FOLD / STREET_CHANGE / HAND_END ...
- `hand_id / state_version`
- `payload：Mapping[str, Any]`（只读映射，金额用 `ChipAmount`）
- `timestamp / source`
- 创建后不可修改；payload 不得被原地修改

## 5.7 HandHistory
- `hand_id`
- `players: tuple[PlayerState, ...]`：本手起手名单
- `events: tuple[StateEvent, ...]`（append-only 事件流，用 tuple 保证不可原地追加）
- `summary`：
  - `final_pot`：`ChipAmount`
  - `winners`：赢家列表
  - `winnings`：各赢家赢得金额，`ChipAmount`（非负）
  - `net_result`：各玩家净盈亏，`ChipDelta`（可正负）
- `start_time / end_time`

## 5.8 EquityReport
- `win_rate / tie_rate`：胜率 / 平局率（float）
- `pot_odds / implied_odds`（float）
- `estimated_ev`：`ChipAmount`
- `method`：enumeration / montecarlo
- `timestamp`

## 5.9 OpponentProfile
- `player_id`
- `vpip / pfr / af（激进度）/ cbet_freq / 3bet_freq / bluff_freq`（float 比率，非金额）
- `sample_size`：样本量
- `last_updated`

## 5.10 StrategyReport
- `action_frequencies`：各动作频率分布（`Mapping[Action, float]`，只读）
- `bet_sizes`：建议下注尺度（`tuple[ChipAmount, ...]`）
- `ev`：`ChipAmount`
- `strategy_source`：cache / preflop_db / precomputed / solver
- `confidence`
- `cache_hit`：是否命中
- `solver_metadata`：若来自 Solver，含后端、节点数、耗时等

## 5.11 ReasoningReport（Poker Reasoning Layer 统一输出，v0.2.1 修订）
> **不保存完整 Chain of Thought**。仅保留可审计的结构化摘要，不要求任何 LLM 暴露/存储私有推理链。
- `analysis_summary`：结构化分析摘要
- `key_factors: tuple[str, ...]`：关键因素列表（如 `"SPR = 2.8"`、`"Hero holds nut flush draw"`、`"Villain sample indicates high turn aggression"`）
- `suggested_action`
- `suggested_size`：`ChipAmount`
- `confidence`
- `source`：poker_skill / mock / 未来自研模型
- `model_metadata`：模型版本、调用信息（不含私有推理链）
- `hand_id / state_version / request_id / timestamp`（携带异步元数据，见 §5.13 RequestContext）

## 5.12 Decision（最终出口）
- `action`：fold / call / raise(+size，尺寸用 `ChipAmount`)
- `confidence`
- `evidence_chain`：由哪些 Report 支撑（Equity / Strategy / Reasoning / Opponent）
- `fast_or_slow`：本决策来自哪条路径
- `timestamp / state_version`

## 5.13 ChipAmount / ChipDelta（值对象，v0.2.1）
> 定义于 `core/value_objects.py`。所有筹码/金额字段的**唯一**合法类型。

### ChipAmount（严格非负值对象）
- 底层：`decimal.Decimal`（Python 标准库，无第三方依赖）
- 属性：immutable、可比较（`==` / `<` / `>`）、可加减
- 约束：**严格非负（拒绝 < 0 的构造）**。任何存量、底池、下注、应付金额都必须 ≥ 0。
- 序列化：支持 `to_dict` / `from_dict`（以字符串或整数最小单位存储，避免浮点）
- **rounding policy**：明确指定（默认 `ROUND_HALF_UP`，小数位数按平台最小筹码单位配置，如 0.01 或最小盲注单位的整数倍）
- 适用字段清单：`stack / pot / bet_size / current_bet / to_call / committed_this_street / committed_this_hand / blind / ante / raise_size / call_amount / winnings(非负部分)`

### ChipDelta（可正负的金额变化值对象）
- 底层：`decimal.Decimal`，与 `ChipAmount` 同级同精度
- 属性：immutable、可比较、可加减
- 约束：**允许正、负、零**，用于表示"金额的变化量/净结果"。
- 与 `ChipAmount` 的关系：`ChipAmount` 与 `ChipAmount` 相减得 `ChipDelta`；`ChipAmount` + `ChipDelta` 需校验结果非负才可回 `ChipAmount`（越界抛 `InvalidStateError`）。
- 序列化：同 `ChipAmount`（无浮点）。
- 适用字段清单：`net_result / profit_loss / chip_change`

## 5.14 PlayerState（v0.2.1 正式定义）
最小稳定字段：
- `player_id`（稳定玩家标识，与 seat 概念分离）
- `seat`（稳定座位编号）
- `position`：`SB / BB / UTG / UTG1 / UTG2 / LJ / HJ / CO / BTN / UNKNOWN`（预留位置枚举，覆盖 6-max 与 9-max，**不写死座位数**）
- `stack`：`ChipAmount`
- `committed_this_street`：`ChipAmount`
- `committed_this_hand`：`ChipAmount`
- `status`：`ACTIVE / FOLDED / ALL_IN / SITTING_OUT / UNKNOWN`
- `has_cards`：bool
- `is_hero`：bool
- `is_dealer`：bool

**设计说明**：`last_action` / `last_action_amount` **不**重复存于 PlayerState，由 `StateEvent` 事件流表达（事件溯源天然可推导"上一步动作"），避免状态与事件双份存储导致不一致。

**PlayerState invariants**：
- `stack`、`committed_*` 均为 `ChipAmount`，非负。
- `player_id` 与 `seat` 是两个独立维度，不得混用；同一 `player_id` 跨手牌稳定，`seat` 随座位轮换。
- `status == FOLDED` 时 `committed_this_street` 不再增长。
- `is_hero` 全场至多一个为真。

## 5.15 RequestContext（异步请求元数据，v0.2.1 新增）
> 所有 Slow Path 异步请求与结果**必须**携带，用于 stale result protection。
- `hand_id`
- `state_version`
- `request_id`（唯一）
- `requested_at`

**stale result protection 规则**：Orchestrator 收到任何 Slow 结果后必须校验：
```
result.hand_id == current_state.hand_id
AND result.state_version == current_state.state_version
AND (request_id == latest_request_id_for_state)
```
不满足任意一项 → 标记 `STALE_RESULT`，**直接丢弃**，不得进入 Decision Engine，不得更新 UI。Solver Adapter、Poker Reasoning Adapter、Decision Update 全部遵守此规则。

---

# 6. Phase 0 ~ Phase 3 开发计划

> 约束不变：单窗口 / 单桌 / 固定平台 / 固定分辨率；不做多桌/自动操作/商业化。

## 6.1 Phase 0 — 地基（完全不接真实截图）
- 目标：用假数据跑通 `Observation → State → Event → Hand Memory → Replay`，并达成**事件可确定性重建**。
- 交付：Core 数据契约、State Engine 纯函数骨架、Hand Memory 事件存储、Orchestrator 骨架（假数据驱动）、假数据剧本 fixtures。
- **验收（确定性核心）**：同一批输入 Event 能 100% 重建相同 PokerState 与 HandHistory。
- **测试场景（全覆盖）**：
  1. Single Raised Pot
  2. 3Bet Pot
  3. 4Bet Pot
  4. Limp Pot
  5. Flop / Turn / River 正常切换
  6. Fold 后 Hand End
  7. All-in
  8. OCR 金额异常（低置信度金额 → UNKNOWN 阻断）
  9. 重复 Observation（去重）
  10. 漏帧（时序补全）
  11. 非法 Pot 变化（底池缩水 → 拦截）
  12. Street 倒退（拦截）
  13. 新 Hand 识别
  14. ChipAmount 精度对账（浮点不可用，decimal 确保 Pot 对账 100% 一致）
  15. 深层不可变（外部 list/dict 修改不得改变 Core Object）
  16. Stale Result Protection（见 §5.15 三条规则）

## 6.2 Phase 1 — 感知链路（能"看到"）
- 目标：接入真实截图，产出带置信度的识别结果。
- 交付：Capture Service、Table Mapping 标定工具、Vision Engine、Confidence Gate。
- 验收（逐字段阈值，见 §8.2）：Hero/Board≥99.5%、Street≥99.9%、Pot/Stack/Bet≥99%、Action≥99%；低置信度字段标记 UNKNOWN 而非猜测。

## 6.3 Phase 2 — 状态与记忆闭环（能"算对"）
- 目标：从识别结果稳定产出正确 PokerState 与历史。
- 交付：State Engine 完整实现（去重/补全/冲突仲裁 + ValidationResult）、Hand Memory 回放、Equity Engine。
- 验收：真实牌局录像重建 HandHistory 逐手一致；Equity 与精确解一致。

## 6.4 Phase 3 — 策略输出闭环（能"给出建议"）
- 目标：产出可解释策略结果并展示。
- 交付：Strategy Engine（Cache/Preflop DB/Precomputed/Solver）、Opponent Model、Poker Reasoning Layer（Mock Adapter 优先）、Decision Engine（融合 + 降级）、UI。
- 验收：普通牌局 ≤500ms 出 Fast 结果；LLM/Solver 不可用可降级；复杂牌局 1~3s 异步出高级建议；UI 可回放。

---

# 7. 实现任务清单 v0.2.1

> 严格顺序，每个 Task 独立可验收。**铁律：先接口 → 再实现 → 再测试 → 通过 → commit → 才进下一 Task。**

### 阶段 A — 地基与数据契约（P0）

| Task | 内容 | 验收 |
|---|---|---|
| **Task 1** | 项目初始化 + Core Domain Model（完整数据契约） | 纯 Python 3.11，零第三方依赖；所有对象字段与不变量有文档 |
| Task 2 | Hand Memory 事件存储（append-only EventStore） | 可完整回放一手牌 |
| Task 3 | State Engine 纯函数骨架 + ValidationResult | 非法状态/倒退/缩水拦截单测通过 |
| Task 4 | Orchestrator 骨架 + 假数据流水线 | 所有 Phase 0 规定场景全部通过（确定性重建 100%） |
| Task 5 | 阈值配置与 Confidence Gate 契约 | 低置信度字段正确阻断并标记 UNKNOWN |

### 阶段 B — 感知（P1）

| Task | 内容 | 验收 |
|---|---|---|
| Task 6 | Capture Service + Table Mapping 标定工具 | 固定窗口稳定截图 + ROI 标注 |
| Task 7 | Vision Engine（手牌/公共牌/金额/行动 OCR） | 黄金样本达逐字段阈值 |

### 阶段 C — 状态/赢率（P2）

| Task | 内容 | 验收 |
|---|---|---|
| Task 8 | State Engine 完整实现接入真实 Vision | 录像重建逐手一致 |
| Task 9 | Equity Engine（枚举 + 蒙特卡洛 + Pot Odds） | 与精确解比对一致 |

### 阶段 D — 策略/推理/出口（P3）

| Task | 内容 | 验收 |
|---|---|---|
| Task 10 | Strategy Engine（Cache + Preflop DB + Precomputed + MockSolver） | 命中缓存时 ≤500ms；Solver 降级可用 |
| Task 11 | Opponent Model（VPIP/PFR/3bet 等基础统计） | 给定历史输出画像 |
| Task 12 | Poker Reasoning Layer（Mock Adapter 优先） | 统一 ReasoningReport；Mock 与未来模型接口一致 |
| Task 13 | Decision Engine（融合 + 规则兜底 + 降级） | 输出带证据链；LLM/Solver 不可用可降级 |
| Task 14 | UI 展示与回放 | 可回放任意历史牌局 |

**禁止项**：
- 多个模块间临时乱 import；
- 为了让测试通过绕过架构；
- 一次改多个 Phase；
- 未经批准提前接 TexasSolver / PokerSkill / UI / 自动操作。

---

# 8. 附录：技术选型与风险

## 8.1 技术选型（v0.2 更新）

| 项 | 选型 | 说明 |
|---|---|---|
| **Python** | **3.11.x（固定）** | `requires-python = ">=3.11,<3.12"`；兼容 OpenCV/OCR/ONNX/PyTorch/TexasSolver/较老 Poker 库，优先稳定性 |
| 数据库 | 开发期 SQLite，Repository 抽象预留 PostgreSQL | 零运维；接口隔离便于迁移 |
| 视觉框架 | OpenCV + 专用轻量分类模型 | 窄领域小模型更快更准 |
| OCR | PaddleOCR + 金额模板匹配 | 固定字体/位置场景更稳 |
| 测试 | pytest + pytest-cov + 黄金样本 + CI | 黄金样本是视觉回归最佳实践 |
| 项目管理 | Git + ADR + monorepo | ADR 记录决策；monorepo 便于联动 |

## 8.2 Vision 验收阈值（v0.2 定稿）

| 字段 | 阈值 |
|---|---|
| Hero Cards | ≥99.5% |
| Board Cards | ≥99.5% |
| Street Detection | ≥99.9% |
| Pot | ≥99% |
| Stack | ≥99% |
| Bet Size | ≥99% |
| Action Detection | ≥99% |

**Confidence Gate 原则**：关键字段低于阈值 → 触发重采样 / 等下一帧 / 标记 UNKNOWN，**绝不进入 Decision Engine**。宁可 UNKNOWN，也不让错误 PokerState 流入 Solver 产生错误 Decision。

## 8.3 风险分析（继承 v0.1 + 强化）

| # | 风险 | 缓解措施 |
|---|---|---|
| 1 | 视觉识别失败 | 逐字段置信度 + Confidence Gate + 重采样 + 黄金样本回归 |
| 2 | Poker State 错误 | State Engine 纯函数 + ValidationResult 硬约束 + 事件溯源可回滚 |
| 3 | 开源整合风险 | Adapter 隔离 + 锁版本 + fork 稳定化 |
| 4 | 性能风险 | Fast/Slow 分离 + Strategy 缓存 + Equity 缓存并行；先准后快 |
| 5 | 后续扩展风险 | 平台隔离在 configs/platform + Table Mapping；自动操作排除在 Phase 外 |
