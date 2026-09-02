# wepoker_android_capture_card — 未标定（UNCALIBRATED）

`platform_id = wepoker_android_capture_card`（采集卡：手机 → 视频适配器 → UVC 采集卡 → PC）。

## 状态：NOT CALIBRATED

本目录目前只有一份**状态清单** `calibration.json`（`status: "uncalibrated"`）。它
**不含任何**字段测量（ROI、阈值、样本数、置信度），也**不得**继承
`wepoker_android`（LDPlayer）或 `wepoker`（H5）的任何结论。

## 已就绪（代码层）

- `src/poker_engine/perceptual/capture/capture_card_backend.py`：UVC 实时采集后端
  （`CaptureCardBackend`），MSMF / DirectShow / YUY2，断流黑屏检测。
- `src/poker_engine/perceptual/capture/normalization.py`：阶段 C 的画面归一化
  （旋转 → 镜像 → 裁剪 → 尺寸验证）。

## 待完成（需真机采集，见 `docs/capture-card-calibration-guide.zh-CN.md` 阶段 A–L）

1. **阶段 A**：冻结硬件与采集环境，写 `device_and_capture.json`。
2. **阶段 B**：录制 45–90 分钟真实对局素材。
3. **阶段 C**：确定 `normalization.json`（旋转/裁剪/输出尺寸）。
4. **阶段 D–G**：抽帧、ROI 测量、逐帧真值标签、最低覆盖。
5. **阶段 H–I**：数据划分、模板与阈值标定。
6. **阶段 J–K**：座位映射、Replay 与性能证据。
7. **阶段 L**：把通过验收的 `configs/platform/wepoker_android_capture_card__<layout_id>.json`
   、`_seat_mapping.json` 以及 `board/dealer/empty/hero_slot_layout.json`、
   隐私安全模板落到本仓库，并接入 `live.py` 管线。

在阶段 L 完成前，任何基于本平台的识别都**必须**读出 `UNKNOWN`，不得宣称端到端可用。
