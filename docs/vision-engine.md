# Vision Engine（Task 7B）

感知层核心：`Frame + TableMap + Vision 配置 → RawObservation`。

## 架构

- `VisionEngine` 只编排，不实现识别算法，不泄漏 OpenCV/Paddle 到 Core。
- 可替换 detector/adapter Protocols：`CardRecognizer` / `AmountRecognizer` / `ActionRecognizer` / `BoardSlotDetector` / `StreetDetector` / `ConfidenceCalibrator`。

## 模块

| 文件 | 职责 |
|---|---|
| `protocols.py` | Protocols + 不可变识别结果 dataclass |
| `card_layout.py` | `BoardSlotLayout`(5) / `HeroSlotLayout`(2)，归一化子 ROI |
| `asset_manifest.py` | `VisionAssetManifest`（版本绑定，JSON round-trip） |
| `calibration.py` | monotonic empirical bins + per-detector `abstain_floor` |
| `trace.py` | `RecognitionTrace`（memory-only） |
| `card_recognizer.py` | 牌面 rank/suit 模板匹配 |
| `amount_recognizer.py` | 数字模板（ChipAmount，禁 float） |
| `action_recognizer.py` | per-seat action 识别 |
| `board_slot_detector.py` | 5 board slot CARD/EMPTY/UNKNOWN |
| `street_detector.py` | street 派生（精确 UNKNOWN/CONFLICT 规则）+ raw_score |
| `engine.py` | `VisionEngine` 编排 |

## 关键边界

- **平台隔离**：Android 与 H5 的 TableMap、slot layout 和校准证据完全分开。相同 WePoker 牌面美术可通过 `template_source` 复用 rank/suit 模板，但不得据此复用 ROI 或置信度。
- **当前 Android 证据**：66 张去重 1440×2560 ADB 帧中，58 张可见 Hero 手牌全部读对，覆盖 23 个不同手牌；8 张非手牌场景全部 abstain。校准计数按不同手牌去除时间相关重复。
- **Hero 定位**：优先使用 Android 固定 ROI；弹窗、结果动画等导致牌面上移时，使用仅限画面下部中央的双白牌动态定位。仍要求两帧确认后才写入新手牌。

- **Street**：5 视觉 board slot 位置派生（EEEEE/CCCEE/CCCCE/CCCCC），非标准模式 → CONFLICT，任一 UNKNOWN → UNKNOWN；与 board_cards 交叉校验。
- **Bet Size**：scalar `bet_size` 仅当恰好一个全局 BET_SIZE ROI（Task 6 契约已结构性保证：BET_SIZE 强制 slot_id=None + 唯一键）。
- **Confidence**：raw score ≠ confidence；per-detector 校准 → `[0,1]`；`abstain_floor` 非 Task 5 阈值。
- **Action**：识别 observed seat-rendered action，非 Hero 可点按钮。
- **确定性**：模板一次初始化；合成 fixture 确定性。

## 不进入

Equity / Strategy / Solver / Decision / LLM / 自动操作 / State mutation / player identity 映射。
