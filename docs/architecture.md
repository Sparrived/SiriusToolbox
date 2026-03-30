# SiriusToolbox 项目架构设计

## 1. 项目目标

- 社媒页面数据采集：通过浏览器自动化模拟真实点击流程，抓取小红书等平台的图文内容。
- 地图 POI 数据采集：通过官方开发者 API 获取高德地图、百度地图等平台的 POI 信息。

设计原则：
- 平台隔离：每个平台独立插件化实现，避免强耦合。
- 采集链路标准化：任务、采集、清洗、存储、导出统一流程。
- 可观测性：日志、指标、失败重试与任务状态可追踪。
- 合规优先：遵守平台条款、隐私与数据使用边界。

## 2. 建议目录结构

建议将仓库逐步演进为以下结构：

sirius_toolbox/
  main.py
  pyproject.toml
  README.md
  docs/
    architecture.md
  src/
    sirius_toolbox/
      __init__.py
      app.py
      settings.py
      core/
        logging.py
        exceptions.py
        types.py
      tasks/
        models.py
        queue.py
        scheduler.py
      browser/
        engine.py
        session.py
        stealth.py
      collectors/
        browser/
          base.py
          xiaohongshu/
            collector.py
            parser.py
            selectors.py
        maps/
          base.py
          gaode/
            client.py
            mapper.py
          baidu/
            client.py
            mapper.py
      pipelines/
        normalize.py
        deduplicate.py
        validate.py
      storage/
        base.py
        sqlite_store.py
        jsonl_store.py
        media_store.py
      exporters/
        json_exporter.py
        csv_exporter.py
      observability/
        metrics.py
        tracing.py
      compliance/
        policy.py
        pii_filter.py
  tests/
    unit/
    integration/

## 3. 分层职责

### 3.1 任务层 tasks

- 统一任务模型：平台、关键词、地理范围、时间范围、分页策略、速率限制。
- 统一调度策略：串行、并发、定时任务。
- 统一失败语义：重试次数、回退策略、死信处理。

### 3.2 采集层 collectors

- browser collectors：用于页面自动化点击、滚动、详情页进入、图文提取。
- maps collectors：用于官方 API 调用、签名、分页、配额控制。
- 各平台 collector 只关心抓取逻辑，不直接关心最终存储。

### 3.3 流水线层 pipelines

- normalize：将不同平台字段映射到统一数据模型。
- deduplicate：按内容哈希、URL、平台 ID 去重。
- validate：基础字段校验、时间合法性校验、经纬度校验。

### 3.4 存储层 storage

- raw 存储：原始响应与页面片段，便于溯源。
- curated 存储：统一模型数据，便于分析。
- 媒体存储：图片、封面、缩略图独立目录或对象存储。

## 4. 统一数据模型（建议）

### 4.1 社媒图文记录 SocialPost

- platform: str
- source_id: str
- title: str
- text: str
- author: str
- publish_time: datetime
- images: list[str]
- tags: list[str]
- url: str
- collected_at: datetime
- raw_ref: str

### 4.2 POI 记录 PoiRecord

- provider: str
- poi_id: str
- name: str
- address: str
- province: str
- city: str
- district: str
- location: {lng: float, lat: float}
- category: str
- phone: str | None
- source_url: str | None
- collected_at: datetime
- raw_ref: str

## 5. 运行模式

- CLI 模式：用于单次任务触发，适合开发和运维。
- 批处理模式：按任务列表批量执行。
- 服务模式：已提供本地 Web 管理界面和异步任务状态查询。

当前状态（2026-03-27）：

- CLI 已初步可用：支持高德/百度 POI 采集任务创建、分页抓取与 JSONL 落盘。
- CLI 已支持小红书关键词采集：按阈值访问帖子并提取文本、图片、链接等结构化字段。
- WebUI 基础版已可用：支持页面表单提交 POI 采集任务与最近结果展示。
- WebUI 基础版已支持小红书关键词任务提交与最近帖子结果展示。
- WebUI 已拆分为多页面导航（主页、POI 页面、小红书页面、各自结果页）。
- WebUI 任务提交已改为异步执行，并提供任务状态页（含状态/进度可视化与自动刷新）。
- main.py 无参数启动时默认进入 WebUI 并阻塞，便于直接作为本地工具使用。
- WebUI 增强能力（鉴权、分页检索）保留为后续迭代目标。

## 6. 关键技术建议

- 浏览器自动化：Playwright（优先）
- HTTP 客户端：httpx
- 数据校验：pydantic
- 重试控制：tenacity
- 日志：structlog 或 logging + JSON Formatter
- 本地存储：SQLite + JSONL（首期）

## 7. 合规与风险控制

- 仅采集有合法访问权限的数据。
- 严格遵守平台服务条款和 robots 政策。
- 不实现绕过登录安全机制、验证码或反爬安全策略的功能。
- 对包含个人信息字段的数据默认做最小化存储与脱敏处理。

## 8. 里程碑建议

- M1：完成任务模型、Playwright 引擎、POI API 客户端、SQLite 存储。
- M2：完成小红书图文采集插件与高德/百度 POI 双通道。
- M3：完成统一数据模型、导出能力、重试与告警。
- M4：补全测试与文档，进入稳定迭代。
