# DeepResearch 项目学习手册

## 第 4 课：结构化行业数据、Text2SQL、资讯采集和前端页面

本课覆盖项目中不属于 DeepResearch 主循环、但对行业信息助手很重要的业务模块：行业统计数据、企业数据、政策数据、自然语言查询、行业新闻、招投标、股票、长期记忆和前端页面状态。

## 1. 行业数据的三张核心表

`backend/app/models/industry_data.py` 定义：

### 1.1 `industry_stats`

保存行业指标的时间序列和地区维度：

```text
industry_name
metric_name
metric_value
unit
year / quarter / month
region
source / source_url
```

它适合回答“某行业某指标历年趋势如何”。

### 1.2 `company_data`

保存企业和财务运营数据：

```text
company_name / stock_code
industry / sub_industry
revenue / net_profit / gross_margin / market_cap
employees / market_share
year / quarter
```

它适合回答“主要企业的营收、利润和市场份额如何”。

### 1.3 `policy_data`

保存政策信息：

```text
policy_name / policy_number
department / level
publish_date / effective_date / expiry_date
category / industry
summary / key_points
impact_level / affected_entities
```

它适合回答“某行业有哪些政策，影响程度和关键要求是什么”。

## 2. 数据库探索页面的数据流

前端 `/database` 页面只展示三张行业表：

```text
industry_stats
company_data
policy_data
```

进入页面后：

```text
authState.isLoggedIn
  -> GET /database/tables
  -> 前端过滤允许展示的表
  -> 选择第一张表
  -> GET /database/tables/{table_name}/data
  -> 分页显示数据
```

后端的 `DatabaseExplorer` 提供：

```text
get_tables()
get_table_schema(table_name)
get_table_data(table_name, limit, offset, order_by, order_dir)
execute_query(sql, limit)
```

表名和排序字段会做标识符校验，只允许字母、数字和下划线；直接 SQL 查询只允许 `SELECT`，还会拒绝 `INSERT`、`UPDATE`、`DELETE`、`DROP`、`ALTER` 等关键字。

这是一层基础防护，但不是完整 SQL 安全体系。生产环境还应使用只读数据库用户、AST 解析、查询超时和资源限制。

## 3. Text2SQL 的完整链路

用户在数据库页面输入：

```text
新能源汽车 2020 到 2024 年的销量趋势是什么？
```

请求路径：

```text
React DatabasePage
  -> POST /database/text2sql
  -> Text2SQLService.query()
  -> LLM 根据表结构生成 JSON
  -> 提取 sql
  -> validate_sql()
  -> 执行 SQL
  -> 返回数据、解释和 visualization_hint
  -> 前端表格展示
```

LLM 被要求输出：

```json
{
  "sql": "SELECT ...",
  "explanation": "查询解释",
  "expected_columns": ["year", "metric_value"],
  "visualization_hint": "line",
  "confidence": 0.95
}
```

`visualization_hint` 目前主要作为结果元数据，前端数据库页主要显示 SQL 和表格，并没有自动把结果渲染成完整图表。这说明“后端生成了可视化建议”不等于“前端已经实现可视化闭环”。

### 3.1 SQL 校验的实际规则

```text
不能为空
必须以 SELECT 开头
禁止危险关键词
不允许多条语句
不允许 SQL 注释
```

如果没有配置数据库连接，`Text2SQLService` 会返回按 SQL 内容判断的模拟数据，用于演示和测试。这种降级会让页面看起来能工作，但不能把模拟结果误认为真实数据库结果。

## 4. 智能数据分析和图表生成

### 4.1 `SmartDataAnalyzer`

它是规则型分析器，不依赖 LLM。主要流程：

```text
输入列表/字典
  -> 统一为 List[Dict]
  -> 根据列名和取值识别类型
  -> 生成数据画像
  -> 自动选择 trend / comparison / distribution / general
  -> 计算统计量和洞察
  -> 给出 visualization_hint
```

它会识别：

```text
NUMERIC     数值
CATEGORICAL 分类
DATETIME    时间
TEXT        文本
BOOLEAN     布尔
```

例如同时存在时间列和数值列时，默认选择趋势分析；存在分类列和数值列时，默认选择对比分析。

### 4.2 `ChartGenerator`

`ChartGenerator` 生成 ECharts 配置，支持：

```text
line / bar / pie / scatter / table
```

后端返回的是配置对象，例如：

```text
type
title
echarts_option
```

前端 `components/chart` 和研究详情的 Visualization 组件负责渲染。图表数据本身通常不需要在浏览器重新计算，前端只消费配置。

一个实现边界是 `merge_configs()` 目前是空实现，因此不能假设多个图表配置已经具备自动合并能力。

## 5. 行业资讯采集

### 5.1 采集来源

`NewsCollectionService` 使用：

```text
Bocha API     采集行业新闻、政策、研报等网页结果
81API         采集招标和中标信息
PostgreSQL    保存规范化后的记录
```

行业配置在 `config/industry_config.py` 中提供行业名称、新闻关键词和招投标关键词。

### 5.2 新闻采集流程

```text
选择行业
  -> 读取 news_keywords
  -> Bocha web-search
  -> 提取 URL、标题、摘要、来源、发布日期
  -> source_url 去重
  -> 规则判断分类
  -> 写入 industry_news
  -> 写入 news_collection_tasks
```

采集任务会记录 `pending/running/completed/failed` 状态、数量和错误信息。分类、部门和日期部分是规则推断，不一定等于来源的正式元数据。

### 5.3 招投标采集流程

```text
读取 bidding_keywords
  -> 81API 查询招标公告
  -> 81API 查询中标信息
  -> 检查 quota_exhausted
  -> bid_id 去重
  -> 解析地区、类型、发布时间
  -> 写入 bidding_info
```

如果 API 配额耗尽，服务会停止继续查询并把原因写入错误列表。这个分支是业务上很重要的外部依赖边界。

## 6. 定时任务和手动采集

应用启动生命周期会调用 `init_scheduler_and_check_data()`：

```text
启动 APScheduler
  -> 添加每天 12:00 的采集任务
  -> 检查数据库是否已有资讯
  -> 没有数据时立即执行一次初始采集
```

路由提供：

```text
GET  /news/list
GET  /news/bidding/list
GET  /news/stats
POST /news/collect
GET  /news/scheduler/status
GET  /news/check
GET  /news/industries
```

前端 `/news` 和 `/bidding` 页面通过这些接口进行分页、筛选和统计展示。

当前实现中，`/news/collect` 虽然声明了 `BackgroundTasks`，但实际直接等待 `collect_all()` 并返回结果；不能仅凭参数名判断它已经异步后台执行。

## 7. 股票服务和政策向量搜索

### 7.1 股票服务

`StockService` 对接聚合数据 API：

```text
纯数字代码 6 开头 -> sh
纯数字代码 0/3 开头 -> sz
已带 sh/sz 前缀 -> 原样使用
```

它支持单只股票实时行情和上海/深圳市场列表。API key 缺失时返回错误，不会生成真实行情。

### 7.2 政策搜索服务

`PolicySearchService` 用 Milvus 保存政策文档字段和向量，提供：

```text
vector_search
keyword_search -> 当前降级为向量搜索
hybrid_search  -> 当前也调用向量搜索
```

所以接口名称虽然包含 keyword/hybrid，当前实现并没有真正的关键词和混合检索算法。面试时应准确说“当前降级策略”，不要把接口名当成实现事实。

## 8. 长期记忆链路

用户可以从 PostgreSQL 会话创建长期记忆：

```text
POST /memories/create
  -> 验证会话属于当前用户
  -> 读取 ChatMessage
  -> LLM 总结摘要、洞察、偏好和主题
  -> 写入 long_term_memories
  -> 对摘要/洞察/主题生成向量
  -> 写入 Milvus long_term_memories 集合
```

查询记忆时：

```text
用户问题
  -> 生成查询向量
  -> Milvus 按 user_id 过滤
  -> COSINE 相似度 top_k
  -> 返回记忆内容和分数
```

PostgreSQL 保存可管理的摘要记录，Milvus 保存便于语义召回的向量。删除记忆时服务还会尝试删除对应的向量，避免数据库和向量库长期不一致。

## 9. 前端路由和状态管理

### 9.1 路由层

`frontend/src/router/routes.tsx` 将页面映射为：

```text
/login
/
/chat
/chat/:id
/knowledge
/memory
/database
/news
/bidding
```

除了 `/login`，主路由包在 `AuthGuard` 和 `BaseLayout` 中。未登录访问时保存原路径，登录成功后可以回到原页面。

### 9.2 请求层

`api/request` 统一创建 Axios/fetch 请求实例，启用：

```text
baseURL = VITE_API_BASE
全局 loading
错误提示
重复请求取消
响应 unwrap
```

认证插件从 `localStorage.auth` 读取 token，并自动设置：

```http
Authorization: Bearer <token>
```

### 9.3 Valtio 状态

项目使用 Valtio：

```text
authState      登录用户、Token
sessionState   会话列表和当前会话
knowledgeState 知识库、文档、上传状态
industryState  行业筛选状态
deviceState    设备状态
```

`authState` 会持久化到 localStorage；会话和知识库状态主要通过 action 调接口后更新内存。

## 10. 一次“数据库自然语言查询”完整数据流

```text
用户在 /database 输入问题
  -> DatabasePage.handleSearch
  -> api.database.text2sql
  -> POST /database/text2sql
  -> Text2SQLService 生成 JSON
  -> validate_sql
  -> PostgreSQL SELECT 或模拟数据
  -> Text2SQLResponse
  -> 页面显示 SQL、解释、行数据和数量
```

这条链与 DeepResearch 的区别是：它不经过六个 Agent，也不通过 SSE；它是一次请求一次响应。

## 11. 一次“新闻页面加载”完整数据流

```text
/news 页面
  -> api.news.getNewsList
  -> GET /news/list
  -> NewsCollectionService.get_news_list
  -> PostgreSQL 筛选和分页
  -> NewsListResponse
  -> 前端列表、统计和筛选器
```

采集和展示分开：展示读数据库，采集才调用外部 API。这样页面加载不必每次都依赖 Bocha 或 81API。

## 12. 本课练习

### 练习一：区分三种查询

判断下面问题应该走哪条链：

```text
A. “2020 到 2024 年新能源汽车销量趋势”
B. “帮我研究新能源汽车产业并写报告”
C. “搜索我上传的政策 PDF 中关于补贴的内容”
```

参考：

```text
A -> /database/text2sql
B -> /research/stream
C -> 知识库/向量检索或附件聊天链路
```

### 练习二：解释为什么页面有数据但采集接口失败

因为新闻页面读取的是 PostgreSQL 已保存数据；采集接口才依赖 Bocha/81API。外部 API 暂时不可用，不会自动删除已有数据库记录。

### 练习三：找出 Text2SQL 的四个安全边界

至少应说出：只允许 SELECT、拒绝危险关键词、拒绝多语句、限制结果数量；更完整的生产方案还需数据库只读账号和查询资源限制。

## 13. 面试检查题

### 初级

- `industry_stats`、`company_data`、`policy_data` 分别保存什么？
- 为什么新闻展示接口不应该每次都调用外部搜索 API？
- Valtio 在前端项目中承担什么作用？

### 中级

- Text2SQL 为什么要先生成 SQL 再验证再执行？
- `source_url` 和 `bid_id` 去重分别解决什么问题？
- 长期记忆为什么同时保存 PostgreSQL 记录和 Milvus 向量？

### 高级

- 如何防止 LLM 生成带有注释、分号拼接或子查询绕过规则的 SQL？
- 如果新闻采集任务执行一半进程崩溃，任务表和业务表可能处于什么状态？如何改进幂等性？
- 如果 `keyword_search` 和 `hybrid_search` 当前都降级为向量搜索，怎样设计真正的混合检索？

## 14. 本课结论

项目的业务层可以概括为：

```text
结构化数据 -> Text2SQL / 数据分析 / 图表
外部资讯   -> 采集 / 去重 / 定时任务 / PostgreSQL
文档知识   -> 解析 / 切片 / Embedding / Milvus
用户记忆   -> LLM 摘要 / 向量召回 / 个性化上下文
前端页面   -> 路由 / 认证守卫 / 请求插件 / Valtio 状态
```

这些模块给 DeepResearch 提供证据和工程基础，也使系统不只是一个简单的聊天页面。

