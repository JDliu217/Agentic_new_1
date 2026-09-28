# DeepResearch 学习手册：第 12 课

## 行业资讯、数据库探索与数据分析

本课覆盖项目中与 DeepResearch 并列的三个能力：行业新闻/招投标采集、数据库浏览、Text2SQL 和图表分析。它们共同构成“结构化行业数据”这条支线。

---

## 1. 行业资讯和招投标链路

### 1.1 页面读取

新闻页面和招投标页面分别读取：

```text
frontend/src/pages/news/index.tsx
frontend/src/pages/bidding/index.tsx
frontend/src/api/news.ts
```

接口：

```text
GET  /news/list
GET  /news/bidding/list
GET  /news/stats
POST /news/collect
GET  /news/industries
GET  /news/industries/{industry_id}
```

页面会把当前行业 ID、分类、公告类型、省份、分页参数发送给后端，然后展示列表、统计卡片和采集结果。

### 1.2 采集链路

```text
POST /news/collect
  → NewsCollectionService.collect_all()
  → get_industry_config(industry_id)
  → 使用行业关键词搜索新闻
  → 创建 IndustryNews
  → 使用招投标关键词/API 搜索
  → 创建 BiddingInfo
  → PostgreSQL commit
  → 返回 collected 数量和错误
```

行业配置位于：

```text
backend/app/config/industry_config.py
```

当前预定义行业包括智慧交通、金融科技、医疗健康和能源电力。每个行业有新闻关键词、招投标关键词和研究关键词。

### 1.3 定时采集

`SchedulerService` 使用 APScheduler，每天 12:00 添加资讯采集任务。应用启动时：

1. 启动调度器。
2. 检查数据库中是否已经有资讯数据。
3. 如果没有数据，执行一次初始采集。

这段逻辑在 `backend/app/app_main.py` 的 lifespan 和 `scheduler_service.py` 中。

### 1.4 当前边界

- 新闻和招投标数据最终写入 PostgreSQL，不是临时直接给页面。
- 招投标采集需要对应 API 配置；未配置时 `collect_all()` 会跳过招投标采集。
- 采集接口虽然定义了后台任务参数，当前路由实际直接等待 `collect_all()` 完成后返回结果。
- 外部 API 配额、搜索结果质量和重复数据会影响采集结果。

---

## 2. 数据库探索页面

文件：

```text
frontend/src/pages/database/index.tsx
frontend/src/api/database.ts
backend/app/router/database_router.py
backend/app/service/database_explorer.py
```

### 2.1 表浏览

页面先调用：

```text
GET /database/tables
```

后端 `DatabaseExplorer.get_tables()` 从 PostgreSQL 的 `information_schema` 获取表名、大小和列数，并对每张表统计行数。

点击表后：

```text
GET /database/tables/{table_name}/schema
GET /database/tables/{table_name}/data
```

前者读取列、主键和索引；后者进行分页查询，并允许安全的列排序。

### 2.2 只读 SQL

```text
POST /database/query
```

`DatabaseExplorer.execute_query()`：

- 只允许以 `SELECT` 开头。
- 拒绝 `INSERT`、`UPDATE`、`DELETE`、`DROP` 等关键字。
- 没有 `LIMIT` 时自动追加限制。

这是应用层保护，生产环境还应使用数据库只读账号和更严格的 SQL 解析/权限控制。

---

## 3. Text2SQL 链路

```text
自然语言问题
  → POST /database/text2sql
  → Text2SQLService.generate_sql()
  → LLM 根据固定 Schema 生成 JSON
  → validate_sql()
  → execute_sql()
  → data、columns、visualization_hint
  → 前端展示表格或图表
```

### 3.1 LLM 看到的 Schema

`Text2SQLService.SCHEMA_DEFINITION` 明确描述三个核心行业数据表：

- `industry_stats`：行业指标和年度/季度数据。
- `company_data`：企业营收、利润、市场份额等。
- `policy_data`：政策名称、部门、级别、日期和影响程度。

因此 Text2SQL 的能力不仅取决于模型，还取决于传给模型的 Schema 是否准确、完整和及时。

### 3.2 SQL 安全链路

```text
LLM 返回 SQL
  → 必须非空
  → 必须以 SELECT 开头
  → 禁止修改和危险关键字
  → 禁止多语句和注释
  → 再执行
```

注意：字符串关键字过滤不是完整 SQL 安全方案。生产环境应结合 SQL AST 解析、数据库只读账号、表级权限、超时和结果上限。

### 3.3 没有数据库连接时的模拟数据

`Text2SQLService.execute_sql()` 在没有初始化 `db_engine` 时会调用 `_get_mock_data()`，按 SQL 中的表名返回演示数据。

这意味着：

- 某些页面在没有真实数据库时仍可能展示结果。
- 看到“成功”不一定证明真实 PostgreSQL 执行过。
- 端到端验证时必须确认是否存在 `db_engine`，并检查数据库日志或返回数据来源。

---

## 4. SmartDataAnalyzer

`smart_analyzer.py` 负责把查询或文本中的数据标准化，再识别分析类型：

```text
数据标准化
  → 列画像和类型识别
  → 趋势/分布/对比/通用分析
  → 统计结果和洞察
```

它不是 LLM 本身，而是一个规则和统计分析服务。LLM 负责生成 SQL 或表达式，SmartDataAnalyzer 负责对数据做程序化分析。

这是一种值得学习的工程分工：能用确定性代码完成的统计，不应全部交给模型猜。

---

## 5. 图表链路

数据分析结果可能产生：

- ECharts 配置。
- Python 生成的图片。
- 结构化表格。

前端 `components/chart/index.tsx` 负责渲染图表配置；DeepResearch 报告页 `process-report.tsx` 会把 Markdown、图表和知识图谱组合到内容块中。

当前 `ChartGenerator.merge_configs()` 仍是空实现，因此不能假设多个图表配置已经具备自动合并能力。

---

## 6. 一条完整的数据分析例子

问题：

```text
比较 2023 和 2024 年新能源汽车销量，并推荐合适的图表。
```

流程：

1. 前端调用 `/database/text2sql`。
2. Router 创建 `Text2SQLService`。
3. LLM 读取行业表 Schema，生成 SELECT 和 `visualization_hint=bar/line`。
4. `validate_sql()` 检查 SQL。
5. 有数据库连接则查询 PostgreSQL；没有连接则可能返回模拟数据。
6. 返回数据、列名和图表建议。
7. 前端根据结果展示表格或 ECharts。

如果问题进入 DeepResearch，它还可能继续被 DataAnalyst 和 CodeWizard 使用，形成“数据库结果 → 分析洞察 → 报告图表”的更长链路。

---

## 7. 本课排错题

### 新闻页面为空

检查行业 ID、PostgreSQL 中 `industry_news` 是否有数据、采集 API 是否配置、`/news/list` 的分页和筛选参数。

### 采集返回成功但数量为 0

检查搜索 API、行业关键词、外部 API 配额、去重逻辑和服务返回的 `errors`。

### Text2SQL 显示成功但数据不对

依次检查 LLM 返回 SQL、固定 Schema、SQL 验证、真实数据库连接和是否走了 `_get_mock_data()`。

### 数据库查询被拒绝

检查是否不是 SELECT、是否含危险关键字、是否包含多语句或注释，以及当前用户是否通过认证。

---

## 8. 本课掌握标准

你应该能画出：

```text
行业配置 → 关键词 → 外部搜索/API → IndustryNews/BiddingInfo → PostgreSQL → 页面分页统计
自然语言 → Text2SQL → SQL 校验 → PostgreSQL/模拟数据 → 分析提示 → 图表
```

还要能解释“模型生成”和“程序执行”之间的边界：LLM 只提出 SQL，服务负责校验和执行；LLM 只提出图表或代码，分析器和执行环境负责得到实际结果。

