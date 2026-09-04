# WorkBuddy + K3：采集卡真机闭环执行任务书

> 执行人：持有 Samsung Galaxy S25 Ultra、视频输出适配器和 UGREEN UVC
> 采集卡的一方。
>
> 当前基线：`main`，至少包含提交 `8ce907d`。
>
> 目标：使用真实采集卡完成生产归一化、座位与动作识别接入、Replay 和性能
> 验收，并把可审核的代码分支和证据交回项目负责人。

## 1. 直接复制给 WorkBuddy + K3 的启动提示词

```text
你现在负责 PokerSense 的采集卡真机识别闭环。先完整阅读仓库根目录 AGENTS.md、
TASK-capture-card-workbuddy-k3.zh-CN.md、
docs/capture-card-calibration-guide.zh-CN.md、
PLAN-capture-card-calibration.zh-CN.md，以及
configs/vision/wepoker_android_capture_card/README.md。

从最新 main（至少包含 8ce907d）新建分支：
feat/capture-card-hardware-closure

必须实际控制这台电脑上的 Samsung Galaxy S25 Ultra、视频输出适配器和 UGREEN
UVC 采集卡完成真机采集、测量、接入和验证。不要只复述计划，不要用手机截图、
微信压缩图片、LDPlayer、H5 或合成数据替代真实采集卡正样本，不要猜测标签或
阈值。缺少真值时返回 UNKNOWN，并生成精确补录清单。

严格按本任务书的阶段 0-6 执行。每完成一阶段，保存产物、SHA-256、命令和结果，
并更新 AGENTS.md Progress log。可以提交并推送工作分支，但不要自行合并 main，
不要发布 Release。原始视频、完整截图、标签工作目录、昵称、头像和联系人信息不得
提交公开 GitHub，只能通过私有渠道交付。

需要真人操作手机、进入牌局、拔插采集卡、确认画面或人工读数时，明确暂停并一次
只要求操作者做一个具体动作；完成后继续，不能用假数据绕过。
```

## 2. 完成定义

只有以下各项同时具备，才可以汇报“采集卡真机闭环完成”：

1. 有真实 UVC 原始流测得、桌面程序可加载的生产 `normalization.json`。
2. 牌面、座位占用、筹码、Dealer、Hero 当前行动者和已完成动作，均使用采集卡
   平台自己的 ROI、模板、阈值和 calibration block。
3. seat/action 已接入生产 `VisionEngine`，不能只存在于校准工具目录。
4. 尺寸错误、断流、黑屏、菜单、遮挡、不确定和冲突均失败关闭为 `UNKNOWN`；
   不得回退到 LDPlayer/H5 配置。
5. 真实采集卡 Replay、人工真值、哈希绑定、30 分钟连续运行和拔插恢复证据齐全。
6. 全量测试、Flake8、差异检查和本机打包通过，工作分支已推送，私有素材另交。

任何一项缺失，必须汇报 `PARTIAL/BLOCKED` 并列出精确缺口，不得声称整套系统
已经打通。

## 3. 阶段 0：基线和分支

```bash
git fetch origin
git switch main
git pull --ff-only origin main
git status --short
git switch -c feat/capture-card-hardware-closure

python3 -m venv .venv
./.venv/bin/pip install -e ".[dev,perceptual,desktop,packaging]"
./.venv/bin/python -m pytest -q
./.venv/bin/python -m flake8 src tests tools
```

- 记录 `git rev-parse HEAD`、操作系统、Python 版本和测试结果。
- 如有不相关本地修改，报告并保留，不得清理或顺手提交。
- 基线失败时先定位并记录，不能跳过。

## 4. 阶段 1：冻结硬件和 UVC 参数

私有数据目录不得放进公开仓库：

```bash
python -m tools.capture_card_calibration.cli init \
  --root capture_card_calibration_YYYYMMDD

python -m tools.capture_card_calibration.cli probe \
  --device 0 --api MSMF
```

完成 `source/device_and_capture.json`，不得保留 `REPLACE_ME`。记录手机/Android、
显示尺寸与 DPI、微扑克版本与主题、视频适配器、采集卡和固件、USB 端口、主机、
采集软件、UVC 分辨率/帧率/像素格式/色彩空间、编码参数，以及所有旋转、镜像、
裁剪、缩放和滤镜状态。

使用稳定的最高原生分辨率和至少 30 fps。关闭缩放、锐化、美颜、降噪、动态裁剪、
叠加层、手机自动旋转及通知浮窗。

交付：`device_and_capture.json`、`source/probe/`、硬件连接说明及各文件 SHA-256。

## 5. 阶段 2：真实视频和定向补录

当前 Profile 已获负责人批准使用两个独立会话，不要求为数量伪造第三个会话，但
必须补足真实识别和可靠性场景：

```bash
python -m tools.capture_card_calibration.cli record \
  --root capture_card_calibration_YYYYMMDD \
  --session session_003 --update-manifest
```

真机操作清单：

1. 2 人和 6–8 人真实牌局，覆盖 Preflop、Flop、Turn、River。
2. 尽量覆盖 Fold、Check、Call、Bet、Raise、All-in、结算和下一手发牌。
3. 覆盖每个视觉 slot 的占用、筹码、Dealer 和动作文字。
4. 覆盖加入、离开、空座、暂离和座位变化。
5. 覆盖菜单、弹窗、聊天、表情、遮挡、切后台及回前台。
6. 至少实际拔插并重连采集卡一次，保留断流、黑屏和恢复全过程。
7. 关键动作保留“发生前—动画中—稳定后”的连续帧。

重点补录 `CHECK`、`BET`、`ALL_IN`、明确的 `hand_end/result` 和更多
`reconnect`。若实战仍未出现，不得伪造；记录实际数量、视频时间戳和缺口。已有
负责人批准的覆盖例外可以保留，但不能豁免归一化、断流恢复或生产接入。

```bash
ffprobe -v error -show_streams -show_format -of json \
  capture_card_calibration_YYYYMMDD/source/raw/session_003.mkv \
  > capture_card_calibration_YYYYMMDD/source/probe/session_003.ffprobe.json
```

交付：原始 MKV、事件日志、ffprobe JSON、场景时间戳清单和 SHA-256。素材经私有
网盘、局域网或移动硬盘交付，禁止微信转发或上传公开仓库。

## 6. 阶段 3：生产归一化

根据真实 UVC 帧生成版本化 `normalization/normalization.json`，顺序固定为：

```text
解码 → 旋转 → 镜像 → 裁剪 → 尺寸和内容边界验证 → PNG
```

- 优先只旋转和裁剪，不缩放，不为识别二次增强。
- 测量每个会话开头、中间、结尾及拔插重连后的内容边界。
- 同一 `layout_id` 边界漂移不得超过 2 个输出像素；超出则拆分 layout 或判定
  链路不合格。
- 把生产 artifact 放到 `build_pipeline(source="capture-card")` 能明确加载的位置。
- 增加缺失、格式错误、源尺寸不匹配、旋转和镜像错误测试。
- 禁止把 498x1080 ROI 直接套在未经验证的 1920x1080 UVC 外框上。

交付：`normalization.json`、边界报告、来源帧和配置 SHA-256、加载路径及测试。

## 7. 阶段 4：seat/action 生产接入和标定

仓库已有牌面融合模型、独立几何、座位映射和校准期 seat/action 工具。不要重写
已验证的牌面模型；把以下字段完整接入生产：八个 slot 的占用、筹码、Dealer、
Hero 当前行动者，以及 Fold/Check/Call/Bet/Raise/All-in 已完成动作。

必须完成：

1. 从人工确认的真实帧提取紧裁剪、隐私安全的模板/输入，不含昵称、头像或桌面。
2. 按手牌和会话隔离 calibration/validation，禁止相邻帧和同一手牌泄漏。
3. 每字段建立独立 calibration block，记录样本数、阈值、margin、版本、资源
   SHA-256、锁定验证及硬负样本结果。
4. 接入 `VisionEngine` 和桌面 live 管线，并保留两帧确认。
5. 动作去重；只有筹码变化和底池证据一致时才能产生 canonical event。
6. 空座、遮挡、动画、菜单、断流、相似动作及候选过近时返回
   `UNKNOWN/CONFLICT`，不能猜。
7. 不得复用 LDPlayer/H5 的 ROI、阈值或验证结论。

增加字段正样本、硬负样本、歧义、尺寸错误、两帧确认、Dealer 冲突、空座变化、
2–8 人映射、动作去重及筹码/底池不守恒拒绝事件测试。

## 8. 阶段 5：真实 Replay 和性能验收

Replay 必须绑定源视频/帧 SHA-256、normalization、TableMap、各字段 calibration、
seat mapping、识别器版本、每帧人工预期、拒绝原因、数据授权与隐私审核，并注明
来自真实采集卡。

目标电脑实测并保存原始结果：

1. 连续运行至少 30 分钟；
2. UVC 解码帧率和丢帧率；
3. 归一化加全字段识别的 p50/p95 延迟；
4. 运行前后内存和持续增长；
5. 采集卡拔出、重插后的错误提示与恢复；
6. 切后台、回前台、黑屏和花屏时的失败关闭与恢复；
7. 多采集设备并存时必须显式选择，不能默选错误设备。

没有负责人批准的性能阈值时，只报告原始数字，不能自行判定“性能通过”。

## 9. 阶段 6：验证、打包和交付

```bash
./.venv/bin/python -m pytest -q
./.venv/bin/python -m flake8 src tests tools
git diff --check
./.venv/bin/pyinstaller packaging/pokersense.spec \
  --distpath dist --workpath build --noconfirm
```

macOS 还需：

```bash
/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' \
  dist/PokerSense.app/Contents/Info.plist
codesign --verify --deep --strict --verbose=2 dist/PokerSense.app
```

更新受影响的中英文 README、capture/replay 文档和 `AGENTS.md`。确认安装包不含
视频、完整帧、标签工作区或个人信息。只提交逐项确认的文件：

```bash
git status --short
git add <逐项确认过的文件>
git commit -m "Complete capture-card hardware recognition closure"
git push -u origin feat/capture-card-hardware-closure
```

不要自行合并 `main`，不要创建 Release。

## 10. 最终回传格式

```text
状态：COMPLETE / PARTIAL / BLOCKED
分支 / 提交 / 基线提交：

硬件：手机、Android、适配器、采集卡、固件、USB、UVC 参数

真机素材：
- 会话数和总时长：
- 2 人/6–8 人覆盖：
- Check/Bet/All-in/Result/Reconnect 数量：
- 私有素材地址和素材包 SHA-256：

生产产物：
- normalization 路径、版本、SHA-256：
- seat/action calibration 路径、版本、SHA-256：
- Replay 路径、版本、SHA-256：

验证：
- pytest / Flake8 / diff check / 打包：
- 30 分钟运行、FPS、丢帧率、p50/p95、内存：
- 拔插和切后台恢复：

未完成项：精确缺口、原因、下一步由谁做什么
```

项目负责人将根据代码差异、锁定验证集、真实 Replay、性能原始记录和隐私检查
审核；审核通过后才会合并 `main` 或考虑发布。
