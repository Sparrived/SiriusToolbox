---
name: sirius-toolbox-version-control
description: SiriusToolbox 版本控制与发布规范，覆盖 .gitignore 审核、变更分析与 commit 生成、CHANGELOG 维护、Action 触发发布。
---

# SiriusToolbox Version Control Skill

## 目标
- 确保运行时数据和本地产物不会进入仓库。
- 基于真实改动自动生成高质量 commit 信息。
- 在提交时同步更新 CHANGELOG。
- 触发 GitHub Actions 自动发布源代码和构建产物。

## 适用场景
- 用户请求关键词包含：提交、commit、版本控制、发布、release、changelog、action、workflow、打 tag。

## 能力 1：检查 `.gitignore`
每次准备提交前，必须执行：
1. 审核 `.gitignore` 是否覆盖运行时数据与构建产物。
2. 对 SiriusToolbox 项目，至少应忽略以下路径：
- `data/raw/`
- `data/curated/tasks/`
- `data/exports/tasks/`
- `dist/`、`build/`、`*.spec`
- `*.log`
3. 若发现缺失，先更新 `.gitignore` 再进行提交。

推荐检查命令：
```powershell
git status --short
```

## 能力 2：分析改动并生成 commit 信息
提交前执行改动分类：
- `feat`: 新功能
- `fix`: 缺陷修复
- `refactor`: 重构
- `docs`: 文档/Skill 更新
- `build`: 构建链路与发布流程
- `chore`: 其他维护项

commit message 规范：
```text
<type>(<scope>): <summary>
```

示例：
- `fix(webui): add direct task html report button`
- `feat(xhs): export engagement fields to social report`
- `build(release): add one-command exe packaging guidance`

生成规则：
1. summary 使用动词开头（add/fix/update/remove）。
2. 控制在 72 字符内。
3. 若变更跨多个模块，优先使用最主要业务范围作为 `scope`。

## 能力 3：提交并生成 CHANGELOG
提交步骤：
1. `git add` 目标文件。
2. 生成并执行 `git commit -m`。
3. 更新 `CHANGELOG.md`（若不存在则创建）。

CHANGELOG 条目格式：
```markdown
## YYYY-MM-DD
- <type>(<scope>): <summary>
```

要求：
- CHANGELOG 条目与 commit 摘要语义一致。
- 若一个提交包含多个独立改动，可在同日期下追加多条 bullet。

## 能力 4：触发 Action 自动发布
默认发布流程：
1. 推送提交与标签。
2. 触发仓库中的 Release Workflow：`.github/workflows/release.yml`。

Release Workflow 约定：
- 支持 `push tags (v*)` 自动触发。
- 支持 `workflow_dispatch` 手动触发（输入 `version`，例如 `v0.1.0`）。
- 输出 release assets：`SiriusToolbox.exe` 与 zip 包。

推荐发布方式（两者二选一，避免重复触发）：

方式 A（推荐，自动触发）：
```powershell
git push origin <branch>
git tag vX.Y.Z
git push origin vX.Y.Z
```

方式 B（手动触发 workflow_dispatch）：
```powershell
git push origin <branch>
gh workflow run release.yml -f version=vX.Y.Z
```

说明：
- 方式 A 由 `on.push.tags: v*` 自动触发。
- 方式 B 由 `workflow_dispatch` 触发，工作流内会在缺失时自动创建并推送该版本 tag。
- 不建议在同一版本同时执行方式 A 和方式 B，以免重复发布。

发布内容要求：
- Source code archive（GitHub 自动）
- 构建产物（例如 `SiriusToolbox.exe`）作为 release asset

## 执行约束
- 禁止使用交互式 git 命令（如 `git commit` 无 `-m`）。
- 禁止将 `data/raw`、`data/curated/tasks`、`data/exports/tasks` 提交到仓库。
- 触发发布前必须确认构建成功且产物存在。
