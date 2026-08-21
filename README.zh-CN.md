# PokerSense

**简体中文** | [English](README.md)

PokerSense 是一款德州扑克实时分析桌面伴随工具。它读取受支持的牌桌画面，识别玩家底牌，并在独立窗口中展示胜率和识别状态。

PokerSense 只负责观察和展示，不控制扑克客户端、不代替用户下注，也不提供自动操作。

## 当前支持范围

当前桌面版本已针对 WePoker H5 单挑牌桌的底牌区域完成标定。

| 功能 | 状态 |
|---|---|
| macOS 与 Windows 桌面安装包 | 可从 [GitHub Releases](https://github.com/windgeek/PokerSense/releases) 下载 |
| 屏幕读取与实时伴随窗口 | 可用 |
| WePoker H5 底牌识别 | 已标定 |
| 胜率计算 | 可用；翻牌前按底牌对随机范围计算 |
| 中英文界面 | 可用；语言选择会在重启后保留 |
| 公共牌、底池、街道 | 尚未标定；界面会显示不可用 |
| 自动打牌或策略建议 | 不提供 |

当连续帧确认到一对不同的底牌时，PokerSense 会自动开始新的一手。发牌动画中的单帧变化不会直接写入状态。

## 安装

请从 [GitHub Releases](https://github.com/windgeek/PokerSense/releases) 下载最新安装包：

- macOS：`PokerSense-macos.dmg`
- Windows：`PokerSense-Setup.exe`

首次需要读取屏幕时，macOS 会请求“屏幕录制”权限。请在 **系统设置 → 隐私与安全性 → 屏幕录制** 中允许 PokerSense，然后返回应用继续使用。权限与安装的应用本身关联；替换或重新构建应用后，可能需要再次授权。

Windows 不会显示“屏幕录制”权限提示；PokerSense 会直接使用 Windows 本地桌面截屏接口。

## 使用 WePoker H5

1. 打开 WePoker H5 牌桌，并保持牌桌可见。
2. 打开 PokerSense；出现系统权限提示时授予“屏幕录制”权限。
3. 在 macOS 上，牌桌需要位于当前正在使用的 Space。
4. 使用前确认伴随窗口顶部显示为已连接或实时读取状态。

目前只有底牌区域完成了平台标定。因此，界面显示的是识别到底牌后的翻牌前胜率，对手范围为随机范围；它不是完整牌局状态分析。

如果同时存在多个标题均为 `WePoker-H5` 的可见窗口，PokerSense 不会自动猜测目标窗口。开发运行时可先列出窗口，再明确指定序号：

```bash
./.venv/bin/python tools/list_windows.py --title WePoker-H5
make run-desktop ARGS="--window-index 0"
```

这个序号来自当前窗口顺序。移动、重开或切换窗口后，请重新查询。

Windows 浏览器追加的窗口标题后缀（例如 ` - Google Chrome`）会自动处理；PokerSense 匹配稳定的页面标题，不绑定某个浏览器名称。

## 隐私与本地数据

屏幕帧只在内存中用于识别，处理后即丢弃。PokerSense 不保存截图、视频或帧历史。

目前唯一会保存的用户设置是界面语言：

- macOS：`~/Library/Application Support/PokerSense/settings.json`
- Windows：`%APPDATA%\\PokerSense\\settings.json`

该文件只保存 `auto`、`en` 或 `zh`。`auto` 会使用系统语言。

## 开发

支持 Python 3.11–3.13。

```bash
# 安装开发依赖
pip install -e ".[dev,desktop,perceptual]"

# 运行检查
make test
make lint

# 启动桌面应用
make run-desktop

# 仅启动本地服务
make run-desktop-server

# 构建本地应用包
pip install -e ".[dev,desktop,packaging]"
make package
```

桌面应用组装代码位于 `src/poker_engine/desktop/`，实时更新链路位于 `src/poker_engine/realtime/`，平台标定位于 `configs/`。

## 识别与标定

PokerSense 使用 OpenCV 模板匹配和按平台配置的布局映射。WePoker H5 的底牌识别已通过留出真实截图验证；标定数据和说明见：

- [`configs/platform/wepoker__h5_2max.json`](configs/platform/wepoker__h5_2max.json)
- [`configs/vision/wepoker/calibration.json`](configs/vision/wepoker/calibration.json)
- [`docs/vision-engine.md`](docs/vision-engine.md)

没有独立标定的数据项会显示为不可用，不会猜测结果。

## 项目结构

| 模块 | 位置 |
|---|---|
| 领域类型与状态转换 | `src/poker_engine/core/`、`src/poker_engine/state_engine/` |
| 截图与视觉识别 | `src/poker_engine/perceptual/` |
| 胜率与实时链路 | `src/poker_engine/equity/`、`src/poker_engine/realtime/` |
| 桌面应用 | `src/poker_engine/desktop/`、`ui/` |
| 测试 | `tests/` |
| 平台标定 | `configs/` |

详细设计说明见 [`docs/`](docs/) 与 [`architecture.md`](architecture.md)。

## 后续计划

1. 完成公共牌、底池和街道的标定。
2. 扩展实时读取在不同桌面环境和牌面皮肤下的覆盖。
3. 降低胜率计算延迟。
4. 在完成数据采集和验证后支持更多平台。
