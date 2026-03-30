---
name: sirius-toolbox-architecture
description: 在 SiriusToolbox 仓库内执行代码生成、重构与问题排查时，遵循本技能定义的架构边界、模块职责和实现优先级。
---

# SiriusToolbox Main Router Skill

本 SKILL 只负责路由，不承载详细规则和更新日志。

## 路由目标
- 根据任务类型，将请求分发到对应子 Skill。
- 确保调用顺序稳定：先路由，再执行子 Skill 规则。

## 子 Skill 映射
1. 架构与实现边界（目录分层、模块职责、平台约束、数据模型、合规、开发优先级）
- d:\Code\SiriusToolbox\.github\skills\sirius-toolbox-architecture-spec\SKILL.md

2. 治理与更新（当前架构快照、变更检查清单、WebUI 编写准则、更新模板、更新日志）
- d:\Code\SiriusToolbox\.github\skills\sirius-toolbox-governance\SKILL.md

3. 构建与分发（Python 3.12 安装引导、EXE 打包、单命令构建）
- d:\Code\SiriusToolbox\.github\skills\sirius-toolbox-build\SKILL.md

4. 版本控制与发布（.gitignore 审核、commit 生成、CHANGELOG、Action 发布）
- d:\Code\SiriusToolbox\.github\skills\sirius-toolbox-version-control\SKILL.md

## 路由规则
1. 若请求涉及“新增/修改功能实现”，先应用 architecture-spec。
2. 若请求涉及“文档同步、检查清单、WebUI规范、架构快照、更新记录”，先应用 governance。
3. 若请求同时涉及代码和同步，两个子 Skill 都要应用：
- 顺序：architecture-spec -> governance。
4. 若发生任何代码变更（新增、修改、删除），必须同步更新相关 SKILL（至少更新 architecture-spec 或 governance 中受影响章节），不得只改代码不改 SKILL。
5. 若请求涉及构建、打包、发布或 EXE 分发，必须额外应用 build Skill：
- 顺序：architecture-spec -> build -> governance。
6. 若请求涉及提交、changelog、git、tag、action/workflow 发布，必须额外应用 version-control Skill：
- 顺序：architecture-spec -> version-control -> governance。

## 主 Skill 约束
- 主 Skill 不再保存当前架构快照。
- 主 Skill 不再保存更新日志。
- 主 Skill 不再保存具体编码细则。
- 每次代码变更后，必须执行“Skill Sync”，在相关子 Skill 中记录规则/边界/快照的更新。
