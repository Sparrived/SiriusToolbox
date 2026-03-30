---
name: sirius-toolbox-architecture-spec
description: SiriusToolbox 架构与实现规范，定义模块边界、平台实现约束与数据模型要求。
---

# SiriusToolbox Architecture Spec Skill

## 目标
- 社媒浏览器采集与地图 API 采集分层解耦。
- 任务、采集、清洗、存储、导出链路统一。
- 保持插件化可扩展，新增平台不破坏既有模块。

## 架构基线
- src/sirius_toolbox/core: 配置、日志、异常、类型
- src/sirius_toolbox/tasks: 任务模型、队列、调度
- src/sirius_toolbox/collectors/browser: 浏览器自动化采集插件
- src/sirius_toolbox/collectors/maps: 地图 API 采集插件
- src/sirius_toolbox/pipelines: 标准化、校验、去重
- src/sirius_toolbox/storage: 原始与结构化数据落地
- src/sirius_toolbox/exporters: 数据导出

## 实施规则
1. 新平台通过 collectors 子插件接入，不直接改动其他平台逻辑。
2. collector 只返回中间结果，不直接写最终存储。
3. 存储必须通过 storage 抽象层。
4. 字段映射必须集中在解析/映射模块，避免重复实现。
5. 所有外部请求必须具备超时、重试和速率控制。
6. 保留 raw_ref 以支持追溯。

## 平台实现约束
### 社媒浏览器采集
- 默认引擎: Playwright。
- 选择器与解析逻辑分离（selectors.py / parser.py）。
- 统一流程: 搜索 -> 列表 -> 详情 -> 结构化输出。

### 地图 POI 采集
- 必须通过官方开发者 API。
- 高德与百度分别封装 client.py + mapper.py。
- API Key 仅来自环境变量或配置文件，不硬编码。

## 数据模型要求
- SocialPost: 图文信息
- PoiRecord: POI 信息

记录需包含:
- 来源平台标识
- 平台原始 ID
- 采集时间
- raw_ref

## 合规要求
- 遵守平台条款与法律法规。
- 不实现绕过认证、验证码或反自动化机制。
- 涉及个人数据时执行最小化收集与脱敏。

## 开发优先级
1. core/tasks/storage 骨架
2. maps API 采集
3. browser 采集
4. pipelines/exporters/observability
