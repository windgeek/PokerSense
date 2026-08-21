# PokerSense

**简体中文** | [English](README.md)

PokerSense 是一款面向授权自建牌局的德州扑克实时训练伴随工具。它读取受支持的牌桌画面，并在独立窗口中
展示分析。当前版本识别玩家底牌并显示翻牌前胜率；v0.3 目标会进一步输出可解释的动作频率、尺度、EV
和置信度。

PokerSense 不是自动打牌机器人：不会点击、输入、下注或控制扑克客户端，真人始终是唯一执行者。目标
场景是朋友自建牌局、对练、教学和刻意训练。

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
| 可解释建议、范围追踪和训练反馈 | 目标架构；尚未实现 |
| 自动打牌或控制客户端 | 永不提供 |

当连续帧确认到一对不同的底牌时，PokerSense 会自动开始新的一手。发牌动画中的单帧变化不会直接写入状态。

## 安装

请从 [GitHub Releases](https://github.com/windgeek/PokerSense/releases) 下载最新安装包：

- macOS：`PokerSense-macos.dmg`
- Windows：`PokerSense-Setup.exe`

首次需要读取屏幕时，macOS 会请求“屏幕录制”权限。请在 **系统设置 → 隐私与安全性 → 屏幕录制** 中
允许 PokerSense，然后返回应用继续使用。权限与安装的应用本身关联；替换或重新构建应用后，可能需要
再次授权。

Windows 不会显示“屏幕录制”权限提示；PokerSense 会直接使用 Windows 本地桌面截屏接口。

## 使用 WePoker H5

1. 打开 WePoker H5 牌桌，并保持牌桌可见。
2. 打开 PokerSense；出现系统权限提示时授予“屏幕录制”权限。
3. 在 macOS 上，牌桌需要位于当前正在使用的 Space。
4. 使用前确认伴随窗口顶部显示为已连接或实时读取状态。

目前只有底牌区域完成了平台标定。因此，界面显示的是识别到底牌后的翻牌前胜率，对手范围为随机范围；
它不是完整牌局状态分析。

如果同时存在多个标题均为 `WePoker-H5` 的可见窗口，PokerSense 不会自动猜测目标窗口。开发运行时可先
列出窗口，再明确指定序号：

```bash
./.venv/bin/python tools/list_windows.py --title WePoker-H5
make run-desktop ARGS="--window-index 0"
```

这个序号来自当前窗口顺序。移动、重开或切换窗口后，请重新查询。

Windows 浏览器追加的窗口标题后缀（例如 ` - Google Chrome`）会自动处理；PokerSense 匹配稳定的
页面标题，不绑定某个浏览器名称。

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

桌面应用组装代码位于 `src/poker_engine/desktop/`，实时更新链路位于 `src/poker_engine/realtime/`，平台标定
位于 `configs/`。

## 识别与标定

PokerSense 使用 OpenCV 模板匹配和按平台配置的布局映射。WePoker H5 的底牌识别已通过留出真实截图
验证；标定数据和说明见：

- [`configs/platform/wepoker__h5_2max.json`](configs/platform/wepoker__h5_2max.json)
- [`configs/vision/wepoker/calibration.json`](configs/vision/wepoker/calibration.json)
- [`docs/vision-engine.md`](docs/vision-engine.md)

没有独立标定的数据项会显示为不可用，不会猜测结果。

## 目标架构

![PokerSense v0.3 目标架构](docs/realtime-training-assistant.drawio.svg)

这个 SVG 内嵌了 draw.io 源数据，可以直接用 draw.io 打开。第一份结果来自确定性的本地 Fast Path；
缓存未命中或 EV 很接近时可异步启动本地 resolver，但过期结果会被丢弃。关键状态不确定时输出
`ABSTAIN`，绝不猜测。

```text
授权牌桌 → Capture → Vision → Temporal Consensus → Confidence Gate
  → State/Event Engine v2 → DecisionContext
  → Range + Equity + Strategy Router → Decision Fusion → Advice → Live Coach UI
  → 真人动作 → Hand Memory → 复盘 / 训练题 → 改善后续牌局先验
```

完整的数据契约、延迟预算、算法说明和里程碑退出标准见 [`architecture.md`](architecture.md)。

## 项目结构

| 模块 | 位置 |
|---|---|
| 领域类型与状态转换 | `src/poker_engine/core/`、`src/poker_engine/state_engine/` |
| 截图与视觉识别 | `src/poker_engine/perceptual/` |
| 胜率与实时链路 | `src/poker_engine/equity/`、`src/poker_engine/realtime/` |
| 桌面应用 | `src/poker_engine/desktop/`、`ui/` |
| 测试 | `tests/` |
| 平台标定 | `configs/` |

更详细的子系统说明见 [`docs/`](docs/)。

## 后续计划

1. **M1 — 可信的 heads-up 完整状态：** 标定公共牌、底池、筹码、行动方和动作；加入多帧共识、下注
   合法性、hand boundary 和筹码守恒。
2. **M2 — 可解释的基础建议：** 落地 `DecisionContext`、组合范围贝叶斯更新、preflop DB、range
   equity、action EV，并把真实 Fast Path 首次建议 p95 控制在 300ms 内。
3. **M3 — 预解库与训练闭环：** canonical solution bundle、EV loss 复盘、漏点分类和训练题；实时与
   局后分析共用同一套接口。
4. **M4 — 鲁棒对手调整：** 小样本向总体先验收缩，用 KL 正则约束剥削偏移，并限制最坏损失。
5. **M5 — 异步局部精算：** 先做 river subgame，设置计算预算并丢弃过期结果。

详细交付物与退出标准见 [`architecture.md` 第 9 节](architecture.md#9-最优实施路线)。
