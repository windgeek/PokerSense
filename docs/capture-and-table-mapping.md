# Capture Service + Table Mapping

感知层第一块（Task 6）：截图采集 + 牌桌 ROI 映射。为 Task 7 Vision 提供 `Frame + ROI crops`，不识别任何扑克内容。

## 模块

- `perceptual/capture/`：`Frame`（不可变帧）、`WindowRect`、`CaptureTarget`、`CaptureService`（抽象）、`FakeBackend`（CI）、`MssBackend`（真实 Windows，manual smoke only）。
- `perceptual/vision/`：`ROIKind` / `ROI` / `TableMap`（含 JSON 序列化）+ `roi.py`（确定性裁剪 + layout 校验）。

## Frame 像素不可变（bytes-backed）

`Frame` 构造时把输入图像经 `ndarray.tobytes()` 复制为**独立 bytes 缓冲**，再用 `numpy.frombuffer` 暴露只读视图。因此：
- 修改 source ndarray 不影响 `frame.image`；
- `frame.image[...] = ...` 抛 `ValueError`；
- `frame.image.setflags(write=True)` 也失败（底层是 immutable bytes）。

不是「冻结 caller 的 ndarray 冒充 immutability」，而是真独立、不可恢复写权限的像素缓冲。

## 坐标体系

四层：screen（虚拟桌面，副屏负坐标合法）/ window / client-area / ROI（normalized 0~1）。TableMap 用 normalized 存储 + `reference_size` 锚；`reference_aspect_ratio` 运行时派生，不持久化。

## layout compatibility

实际帧宽高比与 `reference_aspect_ratio` 偏差超过 `aspect_tolerance` → `TableMapMismatchError` fail fast，不使用错误 ROI。

## per-seat ROI

`ROIKind.STACK` / `ROIKind.ACTION` 携带 `slot_id`（0..N-1），表示**视觉座位槽**，不解释 player identity，不映射 Frozen `PlayerState`。

## 边界

- minimized / closed → `CaptureError`（不 fallback 全屏）。
- occlusion 是 mss backend limitation，不谎称截图恒等于窗口完整内容。
- `Frame → ROI crops` 纯确定性（`int()` floor 舍入）。

## 禁止

OCR / 牌面识别 / 动作识别 / Solver / LLM / Equity / 自动操作 / anti-cheat。
