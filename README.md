# SiriusToolbox

SiriusToolbox 是一个面向数据采集场景的工具箱项目，当前规划包含：

- 社媒图文采集：通过浏览器自动化模拟点击流程，采集小红书等平台的公开图文信息。
- 地图 POI 采集：通过官方开发者 API 获取高德、百度等平台的 POI 数据。

## 项目文档

- 架构设计文档：docs/architecture.md
- 项目技能文档（供 Copilot 协作理解项目边界）：.github/skills/sirius-toolbox-architecture/SKILL.md

## 全新 Windows 机器一键启动

如果电脑是全新环境（未安装 Python、未安装依赖），可在仓库根目录直接双击：

- `start-webui.bat`

该脚本会自动执行以下步骤：

1. 检测 Python 3.12，若缺失则尝试通过 `winget` 自动安装
2. 创建 `.venv` 虚拟环境
3. 检测项目依赖，缺失时自动安装（`pip install -e .`）
4. 安装 Playwright Chromium 运行时
5. 启动 WebUI（默认 `http://127.0.0.1:8787`）

也可以在 PowerShell 手动执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap-webui.ps1
```

可选参数：

- `-SetupOnly`：只初始化环境，不启动 WebUI
- `-SkipPlaywrightInstall`：跳过 Chromium 安装
- `-BindHost 0.0.0.0 -Port 8787`：自定义监听地址与端口

## Release 压缩包一键启动

从 GitHub Release 下载 `SiriusToolbox-vX.Y.Z-windows-x64.zip` 后，解压目录内包含：

- `SiriusToolbox.exe`
- `start-webui.bat`

双击 `start-webui.bat` 即可一键启动 EXE。

## 推荐开发顺序

1. 搭建 core/tasks/storage 基础骨架
2. 接入高德与百度 POI API 采集能力
3. 接入小红书浏览器自动化采集插件
4. 完成数据标准化、导出与可观测性

## 当前可用能力（CLI）

- 通过命令行调用高德/百度官方 API 采集 POI，并写入 data 目录。
- 采集结果同时写入 raw 与 curated（JSONL）存储。
- 支持小红书关键词采集：按阈值访问并提取帖子内容、图片和链接。

示例命令：

```bash
python main.py poi --provider gaode --keyword 咖啡 --city 北京 --page-size 20 --max-pages 2
python main.py poi --provider baidu --keyword 餐厅 --city 上海 --page-size 20 --max-pages 2
python main.py xhs --keyword 护肤 --max-items 15
python main.py export-social --input data/curated/tasks --output-dir data/exports
```

小红书参数说明：

- `--keyword`：搜索关键词
- `--max-items`：访问帖子数量阈值（最多抓取该数量帖子）
- 小红书采集固定以 headed 模式运行（不再提供 headless 选项）
- `--debug`：输出小红书采集调试日志（登录探针、链接发现、错误原因）

调试示例：

```bash
python main.py xhs --keyword 护肤 --max-items 5 --debug
```

环境变量：

- `GAODE_API_KEY`：高德地图 API Key（provider=gaode 时必填）
- `BAIDU_API_KEY`：百度地图 API Key（provider=baidu 时必填）
- `SIRIUS_DATA_DIR`：数据输出目录，默认 `data`

浏览器依赖：

- 首次使用小红书采集前需安装浏览器内核：`playwright install chromium`

导出能力：

- `export-social` 会按任务独立导出（每个任务一个目录）：
  - `data/exports/<task_id>/social_posts.xlsx`（Excel，方便筛选和查看文本字段）
  - `data/exports/<task_id>/social_posts.html`（图文卡片报告，方便直接浏览图片和正文）
  - `data/exports/<task_id>/images/`（自动下载的图片文件）
- 下载图片会统一转换为 `.jpg` 格式，便于在常见工具中打开与分发。

可选参数：

- `--limit N`：仅导出最近 N 条记录
- `--skip-image-download`：跳过图片下载，只导出文本与远程图片链接

任务结果落盘方式：

- 每个任务的结果独立写入：`data/curated/tasks/<task_id>/`（不再累计写入单一文件）。
- 原始数据也按任务隔离：`data/raw/<source>/<task_id>/`。

## 当前可用能力（WebUI）

- 基础 WebUI 已可用：POI 与小红书功能拆分为独立页面，避免单页拥挤。
- 任务提交已改为异步执行：提交后立即返回，不阻塞页面。
- 新增异步任务状态页，支持任务状态/进度可视化与自动刷新。
- `python main.py` 默认直接启动 WebUI，并保持阻塞运行。
- 启动命令：`python main.py webui --host 127.0.0.1 --port 8787`
- 访问地址：`http://127.0.0.1:8787`

WebUI 页面导航：

- `/`：主页导航
- `/poi`：POI 任务提交
- `/xhs`：小红书任务提交
- `/tasks`：异步任务状态页（可视化进度）
- `/poi/results`：POI 结果查看
- `/xhs/results`：小红书结果查看

## 待完成

- WebUI 增强版（分页查询、鉴权）

## 合规提示

- 仅在合法授权和合规场景下采集数据。
- 遵守目标平台服务条款、隐私政策与适用法律法规。
