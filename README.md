# PokerSense (Poker Intelligence Engine)

实时德州扑克 AI 分析助手：观察牌桌 → 理解状态 → 计算胜率 → （后续）给出策略建议。
不是自动打牌机器人，不做录像回放分析。

> 架构基线：`architecture.md` v0.2.1（FROZEN — 改动前先评审，不是不能动）
> 最高设计原则：**正确性 > 稳定性 > 可观测性 > 性能 > 功能数量**

## 模块总览

| 层 | 模块 | 代码位置 | 说明 |
|---|---|---|---|
| 感知 | Capture Service / Vision Engine | `perceptual/` | 截图 + 视觉识别（带置信度证据） |
| 领域 | State Engine / Hand Memory | `state_engine/` `memory/` | 纯函数状态机 + 事件溯源 |
| 实时 | Realtime Pipeline | `realtime/` | FrameSource → Vision → ChangeDetector → State → Equity |
| 推理 | Equity Engine | `equity/` | 枚举 / 蒙特卡洛 / pot odds / 范围 |
| 应用 | Orchestrator | `orchestrator/` | 中央编排（无算法） |
| 门控 | Confidence Gate | `confidence/` | 低置信度阻断为 UNKNOWN |

**尚未实现**：Strategy Engine（fold/call/raise 建议）、Opponent Model（对手画像）、Poker Reasoning（LLM）、Decision Engine、UI。

## 开发

```bash
make install   # 安装依赖（含 dev）
make test      # 运行测试
make lint      # 代码检查
make clean     # 清理缓存
```

Python 版本固定 3.11.x（见 `pyproject.toml`）。

## 目录

见 `architecture.md §3`。

## 当前真实进度（2026-08-20 接手时核实）

已实现且有测试覆盖：

- Core 契约层（不可变值对象 / ChipAmount·ChipDelta / 事件 / 观察）
- Hand Memory（append-only 事件存储，可回放）
- State Engine（纯函数状态机）
- Application Orchestrator
- Confidence Gate
- Capture Service（`FakeBackend` 已跑通；`mss` 真实截屏后端未在本机验证过）
- Vision Engine（模板匹配识别 + 独立的 occupancy/identity 双证据 + 置信度）
- Realtime Pipeline（FrameSource → Vision → ChangeDetector → State → Equity 全链路已打通）
- Equity Engine（枚举 + 蒙特卡洛 + pot odds + 范围，river 两条路径收敛一致）

已知缺口（接手时核实到的，不是猜测）：

1. **没有真实牌桌截图数据**——Vision Engine 目前只在 synthetic/fixture 图片上验证过，没有一张真实平台截图。识别准确率的"验收"结论目前不成立。
2. **Equity 的蒙特卡洛路径是延迟瓶颈**——纯 Python 实现，量级在几百毫秒，全链路预算 500ms 里它吃掉大头，需要换 C 级 evaluator 或向量化。
3. **一个已知的历史测试失败**：`tests/memory/test_hand_memory.py::test_start_hand_none_started_at_auto_utc` 用了硬编码的 UTC 基准时间，会随日历自然过期，与代码逻辑无关。
4. Strategy / Opponent / Reasoning / Decision / UI 全部未开始。

## 参考

- `dickreuter/Poker`（GitHub）——一个完整的视觉+状态+策略+自动操作揉在一起的 bot 项目，仅作**架构与识别技术参考**，不作为依赖引入，也不照搬"自动操作"这条路径（本项目定位是分析助手，不做自动打牌）。
