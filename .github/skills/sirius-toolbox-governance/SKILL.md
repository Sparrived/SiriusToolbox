---
name: sirius-toolbox-governance
description: SiriusToolbox 治理与同步规范，维护架构快照、检查清单、WebUI 准则与更新日志。
---

# SiriusToolbox Governance Skill

## 自动同步原则
代码更新后，必须同步更新治理信息。

硬性规则（不可跳过）：
- 每次代码更新后，必须同时更新相关 SKILL 文档（architecture-spec/governance 中至少一处）。
- 每次代码更新后，必须同步更新 WebUI 版本号常量：`src/sirius_toolbox/webui/server.py` 中的 `WEBUI_VERSION`。
- 未完成 SKILL 同步，不得视为任务完成。

触发条件（任意满足即触发）：
- 新增、删除、重命名目录或模块文件
- 模块职责变化
- 新增跨层依赖或调用链变化
- 新增平台插件/任务模型/存储实现/导出实现
- 配置项、环境变量、启动流程变化

必须执行动作（按顺序）：
1. 更新代码
2. 更新相关 SKILL（architecture-spec/governance）
3. 更新 `src/sirius_toolbox/webui/server.py` 中的 `WEBUI_VERSION`
4. 运行至少一次真实采集测试命令（必须成功）
5. 更新当前架构快照
6. 更新变更检查清单
7. 如整体架构变化，同步 docs/architecture.md 与 README.md

真实测试要求：
- 每次代码变更后必须执行至少一条真实采集测试命令并确认退出码为 0。
- 真实采集测试必须实际访问外部数据源并产生落盘结果（raw 或 curated 的新 task_id 目录）。
- 不允许仅通过单元测试或纯导出命令替代真实采集测试。
- 推荐命令示例：
	- `python main.py xhs --keyword 护肤 --max-items 3 --debug`
	- `python main.py poi --provider gaode --keyword 咖啡 --city 北京 --page-size 20 --max-pages 1`

禁止行为：
- 只改代码不改治理信息
- 保留过期路径或过期职责
- 代码变更后未执行真实采集测试即结束任务

## 当前架构快照（需持续维护）
当前已落地模块：
- main.py: 启动入口，无参数默认启动 WebUI
- start-webui.bat + scripts/bootstrap-webui.ps1: 全新 Windows 机器一键初始化与 WebUI 启动入口（Python 3.12 安装、venv、依赖、Chromium）
- .github/workflows/release.yml: Release 产物同步发布 `start-webui.bat`，zip 解压后可双击启动 EXE
- src/sirius_toolbox/app.py: CLI 参数解析（poi/xhs/webui）、调度与启动
- src/sirius_toolbox/settings.py: 环境变量配置
- src/sirius_toolbox/core: 异常、日志、类型
- src/sirius_toolbox/tasks: 任务模型、队列、调度、POI/社媒处理器
- src/sirius_toolbox/storage: Storage 抽象、JSONL/SQLite 实现
- src/sirius_toolbox/exporters: 社媒数据导出（Excel + HTML 图文报告），按 task_id 独立导出并统一 JPG 图片格式
- src/sirius_toolbox/collectors/maps: 高德/百度 API 客户端与映射
- src/sirius_toolbox/collectors/browser/xiaohongshu: 关键词检索、平滑滚动点击、按 note_id 去重、有限重试、内容/图片提取、登录态检测与等待
- src/sirius_toolbox/webui: 多页面导航（主页、POI、小红书、Task Status），Task Status 集成任务详情/操作历史/结果可视化与异步状态 API，操作历史折叠区支持持续轮询刷新
- tests/unit: 任务队列、JSONL、POI/社媒处理、WebUI记录、XHS解析器、WebUI异步任务状态测试

待落地模块：
- src/sirius_toolbox/pipelines
- src/sirius_toolbox/observability
- src/sirius_toolbox/compliance
- WebUI 增强（分页检索、鉴权）

## WebUI 编写准则
1. WebUI 仅作为交互层，不直接实现采集业务。
2. 所有表单输入必须校验，错误必须明确提示。
3. 关键动作必须记录日志（启动、任务触发、失败）。
4. 页面默认展示最近数据，避免一次性读取大文件。
5. 页面输出必须 HTML 转义，不暴露 API Key。
6. 保持路由、渲染、数据读取解耦，支持后续前后端分离。

## 变更检查清单
- 是否新增或修改平台插件边界
- 是否破坏统一数据模型
- 是否绕开 pipeline 或 storage 抽象层
- 是否同步更新相关 SKILL（至少一处）
- 是否更新 `WEBUI_VERSION`
- 是否补充基础测试
- 是否执行至少一次真实采集测试且命令成功
- 是否更新 docs/architecture.md
- 是否更新当前架构快照
- 是否清理过期路径与职责
- 更新日志条目是否达到压缩阈值并已执行归档

## 更新日志压缩策略
目标：避免 `## 更新日志` 无限制增长，保持 Skill 可读与可维护。

触发阈值：
- 当 `## 更新日志` 条目数 > 40 时，必须执行一次压缩。

压缩规则：
1. 保留最近 20 条明细在 `## 更新日志`。
2. 将更早条目迁移到归档文件：`.github/skills/sirius-toolbox-governance/CHANGELOG_ARCHIVE.md`。
3. 在 `## 更新日志` 顶部新增一条摘要索引，格式如下：
	- `YYYY-MM-DD: 历史日志已归档（N 条）到 CHANGELOG_ARCHIVE.md，摘要：<主题1>/<主题2>/...`
4. 归档文件按时间倒序维护，禁止删除历史事实，仅允许合并同日同类低风险重复项（如纯文案修正）。

执行时机：
- 在“更新代码 -> 更新 Skill”阶段完成压缩，且与本次变更一并提交。
- 若本次变更未触发阈值，则只追加新日志，不做压缩。

禁止行为：
- 达到阈值后继续只追加不压缩。
- 压缩时丢失关键事实（架构边界变化、行为变化、验证结论）。

## 更新模板
- Change: <本次结构变化>
- Impact: <影响模块>
- Skill Sync: <已更新章节>
- Skill Files: <本次同步的 SKILL 文件路径>

## 更新日志
- 2026-04-01: 增强 `scripts/bootstrap-webui.ps1` 依赖检测，启动前先探测 Python 库是否缺失，仅在缺失时执行 `pip install -e .`，避免一键启动流程直接进程序且未校验依赖；同步更新 `README.md`、`CHANGELOG.md` 与 `WEBUI_VERSION`。
- 2026-04-01: 更新 `release.yml`，在 Release 附件与 zip 中同步发布 `start-webui.bat`（直启 `SiriusToolbox.exe`），实现构建后一键启动方式随发布产物分发；同步更新 `README.md`、`sirius-toolbox-build` Skill、`CHANGELOG.md` 与 `WEBUI_VERSION`。
- 2026-04-01: 新增 `start-webui.bat` 与 `scripts/bootstrap-webui.ps1` 一键启动链路，支持全新 Windows 机器自动安装 Python 3.12（winget）、创建虚拟环境、安装依赖与 Chromium 并启动 WebUI；同步更新 `README.md`、`sirius-toolbox-build` Skill 与 `WEBUI_VERSION`。
- 2026-03-30: 统一 `sirius-toolbox-version-control` Skill 的 release 推送逻辑，与 `.github/workflows/release.yml` 保持一致：明确“push tag 自动触发”和“workflow_dispatch 手动触发”为二选一流程，避免同版本重复发布；同步更新 `WEBUI_VERSION`。
- 2026-03-30: 新增 GitHub Action 工作流 `.github/workflows/release.yml`，支持 tag(`v*`) 与手动 `workflow_dispatch` 触发，自动构建 Windows EXE 并发布 Release 附件（`SiriusToolbox.exe` + zip）；同步 `sirius-toolbox-version-control` Skill 的发布约定并更新 `WEBUI_VERSION`。
- 2026-03-30: 新增 `sirius-toolbox-version-control` Skill，覆盖 `.gitignore` 审核、改动分析与 commit 生成、CHANGELOG 维护、Action 发布触发；并在主路由 Skill 与 copilot 指令中接入该能力链路；同时加固 `.gitignore` 以忽略运行时数据目录（`data/raw`、`data/curated/tasks`、`data/exports/tasks`）及构建/缓存产物；同步更新 `WEBUI_VERSION`。
- 2026-03-30: 小红书采集新增 Chromium 运行时自动安装能力：当检测到浏览器可执行缺失时自动尝试执行 `python -m playwright install chromium`（并回退 `playwright install chromium`），失败时返回明确指引；新增环境开关 `SIRIUS_AUTO_INSTALL_CHROMIUM`（默认开启）；同步更新 `WEBUI_VERSION`。
- 2026-03-30: 新增构建与分发 Skill（`sirius-toolbox-build`），沉淀 Python 3.12 安装引导、EXE 单命令构建与失败排查；并在主路由 Skill 与 copilot 指令中接入该 Skill 以覆盖 build/package/exe 场景。
- 2026-03-30: 在 Task Status 的 Task Output Visualization 区域新增 `Open Task HTML Report` 按钮，支持直接打开 `/data/exports/tasks/<task_id>/social_posts.html`；同时前端轮询刷新时保留按钮展示，并补充 `.html` 静态资源 `Content-Type` 为 `text/html`；同步更新 `WEBUI_VERSION`。
- 2026-03-30: 将详情页扩展字段同步到 `social_posts.html` 卡片展示，新增作者标识/主页链接、互动统计（like/collect/comment/share）和帖子附加信息（note_type/ip_location），实现与 `social_posts.xlsx` 一致的信息可见性；同步更新 `WEBUI_VERSION`。
- 2026-03-30: 修复详情统计识别中 `like/comment/share` 的 `\\d` 正则转义，清理剩余 `invalid escape sequence` 告警；同步更新 `WEBUI_VERSION`。
- 2026-03-30: 修复互动数字提取正则的 `\\d` 与小数匹配转义，消除 `collector.py` 运行时 `invalid escape sequence` 警告；同步更新 `WEBUI_VERSION`。
- 2026-03-30: 修复详情页统计文本清洗正则中的 `\\s` 转义，消除 `collector.py` 在运行时的 `invalid escape sequence` 警告并保持互动数字段提取稳定；同步更新 `WEBUI_VERSION`。
- 2026-03-30: 修复小红书详情字段提取中作者主页正则的转义写法，消除 `collector.py` 的 `invalid escape sequence` 警告，保持新增扩展字段提取稳定；同步更新 `WEBUI_VERSION`。
- 2026-03-30: 小红书详情点击采集新增扩展字段（`author_id/author_profile_url/note_type/ip_location` 与 `like/collect/comment/share` 文本+数值），`parse_note` 保留扩展字段并在 `social_posts.xlsx` 增加对应列，支持从帖子详情页直接落盘更多可用信息；同步更新 `WEBUI_VERSION`。
- 2026-03-30: 扩展 `social_posts.xlsx` 导出字段，补充 platform/url_host/local_post_path/tags_count/local_image_count/text_length/extra_fields_json 等可得信息；新增 `publish_time` 多源回填（字段候选 + 正文尾部日期提取）并写入 `publish_time_source`；同步更新 `WEBUI_VERSION`。
- 2026-03-30: 修复 WebUI 页面模板中 `<style>` 起始段缺失导致 CSS 文本外露的问题，补齐 `:root` 样式变量定义并恢复页面正常渲染；同步更新 `WEBUI_VERSION`。
- 2026-03-30: WebUI 的 XHS 提交表单移除 `Browser Mode / headed (fixed)` 展示区域，保持固定 headed 行为但不再暴露无效选择项；同步更新 `WEBUI_VERSION`。
- 2026-03-30: 小红书正文图片提取新增“表情/贴纸”过滤策略（class/alt/URL 关键词 + 小尺寸图片剔除），导出仅保留帖子正文图片，减少 `emoji/sticker` 类图片进入 `social_posts.xlsx` 与导出图片目录；同步更新 `WEBUI_VERSION`。
- 2026-03-30: 修复小红书采集打开 `search_result/<id>` 导致详情图片缺失的问题；新增详情链接归一化（自动转为 `explore/<id>` 并补齐 `xsec_source=pc_search`）后再执行解析，提升 `images` 提取成功率；同步更新 `WEBUI_VERSION`。
- 2026-03-30: 修复小红书详情图片提取链路，增强懒加载属性（srcset/data-src/data-original/data-xhs-img）与背景图样式（background-image）解析，降低 `images=[]` 导致导出 `image_count=0` 的误判；同步更新 `WEBUI_VERSION`。
- 2026-03-30: 修复 Task Status 前端脚本中的换行分割转义问题（`split(/\\r?\\n/)`），避免 JS 语法中断导致 Task Detail 与 Task Operation History 无法实时刷新；改为基于字符码的无转义分割实现并更新 `WEBUI_VERSION`。
- 2026-03-30: Task Status 恢复即时更新（轮询模式），并将 Task Operation History 调整为“最新 3 条直接显示，其余折叠显示”。
- 2026-03-30: 清理 WebUI 全部即时显示逻辑（轮询、SSE、实时日志接口消费），Task Status 改为纯服务端快照渲染。
- 2026-03-30: 新增任务记录推送方法 `_push_task_records_to_webui`，统一整理任务日志与结果记录并一次性下发给页面渲染。
- 2026-03-30: Task Operation History 回退为全量展示模式，移除“最近步骤 + 更早步骤折叠”渲染，首屏与实时刷新均显示全部日志。
- 2026-03-30: WebUI 底部新增版本显示（`WebUI Version`），并新增规则要求每次代码改动后必须更新 `WEBUI_VERSION`。
- 2026-03-30: Task Operation History 新增独立日志实时接口 `/api/task-logs/<task_id>` 与前端高频日志拉取通道，日志刷新不再依赖任务状态刷新链路。
- 2026-03-30: Task Status 新增独立前端心跳脚本（每秒更新时间戳）作为实时链路兜底，避免 Last Live Tick 长时间停留在 '-'。
- 2026-03-30: Task Status 轮询改为持续刷新（运行中高频、结束后低频），修复 Task Operation History 折叠区非实时更新问题。
- 2026-03-30: XHS 任务完成后自动导出到 `data/exports/tasks/<task_id>/`，图片统一转换为 JPG，文本与结构化字段写入 `social_posts.xlsx`。
- 2026-03-30: 新增硬性规则：每次代码变更必须同步更新相关 SKILL（architecture-spec/governance），未完成 Skill Sync 不得结束任务。
- 2026-03-30: WebUI 结果页路由收敛至 Task Status：移除 POI Results/XHS Results 独立入口，统一在 Task Status 展示任务结果。
- 2026-03-30: WebUI Task Status 新增任务操作历史（含状态/进度/成功失败）与任务输出可视化（POI 表格预览、XHS 卡片/本地图片预览）。
- 2026-03-30: WebUI 异步任务 ID 与业务 task_id 对齐，修复点击 TaskID 后无法匹配对应任务输出的问题。
- 2026-03-30: XHS 任务结果增强为按 task_id 隔离落盘帖子与图片（post.json + images），并回填 local_post_path/local_images 字段。
- 2026-03-30: XHS 点击流增强：按 note_id 去重、有限重试、分段平滑滚动，降低重复点击与界面顿挫感。
- 2026-03-29: 主 Skill 拆分完成，主 Skill 改为路由中枢；治理与快照迁移至本 Skill。
- 2026-03-29: WebUI 改为多页面导航，POI/XHS 提交和结果页分离。
- 2026-03-29: XHS 采集新增登录态检测与等待；用户关闭浏览器时任务立即终止并在 WebUI 提示。
- 2026-03-29: WebUI 采集提交改为异步执行，新增任务状态页与可视化进度，提供 /api/tasks 状态接口。
- 2026-03-29: XHS 采集增强搜索链接发现策略，登录后自动刷新搜索页；无结果时改为明确失败原因提示。
- 2026-03-29: 新增 XHS Debug 模式（CLI/WebUI）与登录/风控探针日志，支持通过控制台定位采集失败根因。
- 2026-03-29: XHS 结果链接去重改为保留带 xsec_token + xsec_source=pc_search 的 URL，避免无 token 直链导致 note 内容缺失。
- 2026-03-29: XHS 采集移除 headless 选项，CLI/WebUI 均固定 headed 模式以避免不可访问问题。
- 2026-03-29: XHS 采集主流程改为模拟点击结果卡片进入详情页，优先获取带 xsec_token 的真实详情 URL，并保留兜底打开链路。
- 2026-03-29: 新增 export-social 导出能力，将社媒 JSONL 导出为 Excel 和 HTML 图文报告，便于阅读与查看图片。
- 2026-03-29: 治理规则新增硬性要求：每次代码更新后必须通过至少一次 CLI 验证再结束任务。
- 2026-03-29: export-social 新增图片本地下载（images 目录）与字段回填（标题缺失时从正文生成摘要），提升可读性与离线查看体验。
- 2026-03-29: XHS 图片提取改为正文图片优先，过滤头像/热搜缩略图；任务结果改为按 task_id 独立目录存储（raw/curated）。
- 2026-03-29: export-social 增加旧数据兼容回退（默认 tasks 目录不存在时自动读取 legacy social_post.jsonl）。
- 2026-03-29: 治理规则升级为“每次代码更新后必须执行至少一次真实采集测试”，禁止仅以单测或纯导出命令替代。
- 2026-03-29: export-social 输出改为按 task_id 独立目录（每任务独立 HTML/Excel/images），并将下载图片统一转换为 JPG。
