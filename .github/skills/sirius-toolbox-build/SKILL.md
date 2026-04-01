---
name: sirius-toolbox-build
description: SiriusToolbox 构建与分发规范，提供 Python 3.12 安装引导、EXE 打包流程与单命令构建入口。
---

# SiriusToolbox Build Skill

## 目标
- 让维护者仅安装 Python 3.12 即可完成打包。
- 让最终用户开包后直接双击 EXE 使用（无需额外安装项目依赖）。
- 对未安装 Python 的维护者提供明确安装引导。

## 适用场景
- 用户请求关键词包含：构建、打包、发布、exe、可执行文件、installer、build。
- 需要在 Windows 产出单文件可执行程序。

## 环境前置
- 操作系统：Windows 10/11
- Python：3.12.x（必须）
- 建议：系统可用 `py` 启动器

## Python 3.12 安装引导（无 Python 用户）
优先推荐：
- `winget install -e --id Python.Python.3.12`

安装后验证：
- `py -3.12 --version`

若 `py` 不可用，可使用：
- `python --version`

## 全新机器一键启动（开发态）
在仓库根目录直接运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\bootstrap-webui.ps1
```

或双击：
- `start-webui.bat`

脚本行为：
- 自动检测并安装 Python 3.12（通过 winget）
- 自动创建 `.venv`
- 自动安装项目依赖与 Playwright Chromium
- 自动启动 WebUI

可选参数：
- `-SetupOnly`：仅初始化，不启动
- `-SkipPlaywrightInstall`：跳过 Chromium 安装
- `-BindHost` / `-Port`：自定义监听地址

## 单命令构建（推荐）
在仓库根目录执行以下命令：

```powershell
py -3.12 -m venv .venv; .\.venv\Scripts\python -m pip install -U pip; .\.venv\Scripts\python -m pip install -e . pyinstaller; .\.venv\Scripts\python -m playwright install chromium; .\.venv\Scripts\pyinstaller --noconfirm --clean --onefile --name SiriusToolbox --add-data "src/sirius_toolbox;src/sirius_toolbox" main.py
```

产物路径：
- `dist\SiriusToolbox.exe`

## 使用与分发说明
- 维护者：仅需 Python 3.12，即可执行上方单命令完成打包。
- 最终用户：直接运行 `dist\SiriusToolbox.exe`。
- 首次运行涉及小红书浏览器采集时，若环境缺失 Chromium，请在构建阶段确保已执行：
  - `python -m playwright install chromium`

Release 发布产物要求：
- 附件至少包含：`SiriusToolbox.exe`、`SiriusToolbox-<version>-windows-x64.zip`
- zip 内至少包含 `SiriusToolbox.exe`

## 失败排查
1. `No module named ...`
- 重新执行依赖安装：`python -m pip install -e . pyinstaller`

2. `py` 命令不存在
- 使用 `python` 替代，或重装 Python 并勾选 PATH / py launcher。

3. EXE 启动后缺资源
- 确认打包命令包含：`--add-data "src/sirius_toolbox;src/sirius_toolbox"`

## 约束
- 不得降低 Python 版本要求到 3.12 以下。
- 不得提供多步骤、含糊的构建入口，优先维护“单命令构建”。
