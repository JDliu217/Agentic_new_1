# DeepResearch 学习手册·第 29 课

## Text2SQL、数据库浏览与图表分析的真实边界

本课把项目里的数据库能力拆开，回答四个问题：

1. 数据库页面如何读取表和表数据？
2. 用户输入自然语言后，SQL 是怎样生成和执行的？
3. 没有真实 PostgreSQL 时为什么仍然可能看到结果？
4. 项目里的智能分析器和图表生成器，是否已经和数据库页面组成完整闭环？

源码依据：

```text
D:\课\s4-6\industry_information_assistant\frontend\src\pages\database\index.tsx
D:\课\s4-6\industry_information_assistant\frontend\src\api\database.ts
D:\课\s4-6\industry_information_assistant\backend\app\router\database_router.py
D:\课\s4-6\industry_information_assistant\backend\app\service\database_explorer.py
D:\课\s4-6\industry_information_assistant\backend\app\service\text2sql_service.py
D:\课\s4-6\industry_information_assistant\backend\app\service\smart_analyzer.py
D:\课\s4-6\industry_information_assistant\backend\app\service\chart_generator.py
D:\课\s4-6\industry_information_assistant\backend\app\service\tool_executor.py
```

---

## 1. 先区分两类数据库功能

项目里至少有两条不同的路径：

```text
数据库浏览：
GET /database/tables
GET /database/tables/{table_name}/data
POST /database/query

自然语言查询：
POST /database/text2sql
```

数据库浏览是“用户选择表，读取表结构或分页数据”。Text2SQL 是“用户提出自然语言问题，模型生成 SQL，再执行查询”。两者都在数据库路由下，但不能把它们当成一个函数。

另外，Agent 工具执行器还注册了：

```text
TEXT2SQL
DATA_ANALYZER
CHART_GENERATOR
```

这三项可以被 ReAct 工具链调用，但它们和数据库页面的调用关系并不是自动存在的。判断闭环是否成立，要继续追踪具体调用者，而不能只因为类名和工具名存在就认为页面已经使用了它们。

---

## 2. 数据库页面的加载过程

用户打开数据库页面后，前端首先检查登录状态：

```text
authState.isLoggedIn
  → api.database.getTables()
  → GET /database/tables
  → 后端 DatabaseExplorer.get_tables()
```

页面只保留三个允许展示的表：

```text
industry_stats
company_data
policy_data
```

这是一层前端展示过滤。它控制左侧列表显示什么，但不是数据库级权限控制；后端接口本身仍然需要认真检查表名和用户权限。

用户选择表后，前端按 `pageSize=20` 计算 `offset`：

```text
GET /database/tables/{table_name}/data
    ?limit=20&offset=(page-1)*20
```

返回的数据包括：

```json
{
  "table_name": "industry_stats",
  "columns": ["industry_name", "metric_name", "metric_value"],
  "rows": [{"industry_name": "...", "metric_value": 100}],
  "total": 120,
  "limit": 20,
  "offset": 0
}
```

页面把英文列名映射为中文显示名，同时保留英文列名作为小字说明。这个过程只是展示层转换，不会修改数据库字段。

---

## 3. `/database/text2sql` 的完整执行链

用户在页面输入：

```text
智慧交通 2024 年市场规模是多少？
```

前端按回车或点击查询，调用：

```text
api.database.text2sql(question)
  → POST /database/text2sql
```

后端路由要求登录用户，并从环境变量构造数据库连接：

```text
DATABASE_URL
```

如果没有 `DATABASE_URL`，代码会尝试使用：

```text
POSTGRES_HOST
POSTGRES_PORT
POSTGRES_USER
POSTGRES_PASSWORD
POSTGRES_DB
```

然后创建 `Text2SQLService`，当前路由指定模型为 `qwen-plus`。服务的主入口是：

```text
Text2SQLService.query(question, intent)
```

内部顺序固定为：

```text
1. generate_sql()       使用 LLM 生成 JSON
2. validate_sql()       做字符串级安全检查
3. execute_sql()        真实数据库或模拟数据
4. 组装返回对象
```

可以把它画成：

```text
自然语言问题
    ↓
Schema + Prompt + LLM
    ↓
{sql, explanation, expected_columns, visualization_hint, confidence}
    ↓
SQL 字符串校验
    ↓
SQLAlchemy 执行 / mock 数据
    ↓
{success, sql, data, columns, row_count, ...}
    ↓
React 页面展示
```

---

## 4. Prompt 给了模型什么约束

`SCHEMA_DEFINITION` 在代码中写死了三张可查询表及其主要列：

```text
industry_stats
company_data
policy_data
```

Prompt 要求模型：

```text
只生成 SELECT
使用 PostgreSQL 语法
结果限制在 100 条以内
趋势分析按 year、quarter 排序
返回严格 JSON
给出解释、列名、可视化提示和 confidence
```

这里要理解一个重要边界：Prompt 是给模型的行为要求，不是数据库服务器的强制约束。模型可能没有遵守，因此后面仍然需要程序校验，数据库账号也应该使用最小权限。

---

## 5. `validate_sql()` 做了什么，没做什么

当前实现主要进行字符串检查：

```text
拒绝 DROP、DELETE、UPDATE、INSERT、TRUNCATE 等关键词
要求 SQL 去除空白后以 SELECT 开头
不允许中间出现分号
不允许 SQL 注释
拒绝若干系统表和延时函数关键词
```

它能拦截很多明显的危险输入，但它不是完整的 SQL 解析器，也没有做到：

```text
解析 SQL AST
精确判断每一张表和每一列
强制所有查询都有 LIMIT
强制数据库连接只读
强制真实返回行数不超过 100
```

尤其要注意最后两点。Prompt 要求模型把结果限制在 100 条以内，但真实数据库执行路径使用 `fetchall()`，服务层没有再次加 `LIMIT` 或截断。因此“模型被要求限制 100 条”和“程序必然只返回 100 条”不是一回事。

---

## 6. 真实 PostgreSQL 与模拟数据分支

`execute_sql()` 在通过校验后判断 `self.db_engine`：

```text
有 db_engine
  → SQLAlchemy 建立连接
  → conn.execute(text(sql))
  → fetchall()

没有 db_engine
  → _get_mock_data(sql)
```

`_get_mock_data()` 会根据 SQL 文本中是否出现 `industry_stats`、`company_data`、`policy_data` 等字符串，返回预先写好的演示数据。

所以在以下条件下，接口可能仍然返回 `success=true`：

```text
LLM 能生成合法 SELECT
SQL 通过字符串校验
数据库连接没有建立
```

这时看到的是演示数据，不是 PostgreSQL 中实时读取的数据。排查时必须查看：

```text
DATABASE_URL 是否存在
SQLAlchemy 是否成功创建 engine
数据库服务是否可连接
结果是否命中了 _get_mock_data()
```

不能仅凭页面出现数据，就断定真实数据库已经接通。

---

## 7. 返回到页面的字段

路由将服务结果整理成 `Text2SQLResponse`：

```json
{
  "success": true,
  "sql": "SELECT ...",
  "explanation": "...",
  "data": [{"year": 2024, "metric_value": 3200}],
  "columns": ["year", "metric_value"],
  "visualization_hint": "line",
  "confidence": 0.95,
  "row_count": 1,
  "error": null
}
```

数据库页面目前实际使用这些信息：

```text
sql              → 显示生成的 SQL
explanation      → 显示解释
columns/data     → 拼成结果表格
row_count        → 显示结果数量
error            → 显示错误
```

页面代码没有把 `visualization_hint` 传给 ECharts，也没有在这条查询结果路径中调用 `ChartGenerator`。因此当前用户看到的是表格结果，即使后端告诉模型推荐 `line` 或 `bar`。

---

## 8. SmartDataAnalyzer 和 ChartGenerator 的位置

`SmartDataAnalyzer` 是一个本地 Python 分析器，能够：

```text
标准化字典、文本列表和简单值列表
识别时间、数值、分类、文本和布尔列
计算最小值、最大值、平均值、总和和标准差
尝试识别趋势、分布和对比
输出 insights、statistics、data_profile
推荐 visualization_hint
```

`ChartGenerator` 负责生成 ECharts 兼容配置，支持：

```text
line
bar
pie
scatter
table
```

在 `tool_executor.py` 中，Agent 可以分别调用：

```text
execute_data_analyzer()
execute_chart_generator()
```

这说明项目具备“数据分析工具”和“图表配置工具”的代码资产。但从当前数据库页面可以确认的事实是：

```text
数据库页 → Text2SQL → 表格渲染
```

而不是已经确认的：

```text
数据库页 → Text2SQL → SmartDataAnalyzer → ChartGenerator → ECharts
```

此外，`ChartGenerator.merge_configs()` 当前函数体是 `pass`，所以不能把它描述成已经完成多图表配置合并。

---

## 9. 三条链路的对照表

| 链路 | 入口 | 核心执行 | 页面/调用方的当前结果 |
|---|---|---|---|
| 表列表 | `GET /database/tables` | `DatabaseExplorer.get_tables()` | 左侧表列表 |
| 表数据 | `GET /database/tables/{name}/data` | `DatabaseExplorer.get_table_data()` | 分页表格 |
| 自然语言查询 | `POST /database/text2sql` | LLM → 校验 → 真实库或 mock | SQL、解释、结果表格 |
| Agent 数据分析 | 工具 `DATA_ANALYZER` | `SmartDataAnalyzer.analyze()` | 取决于 Agent 调用方 |
| Agent 图表生成 | 工具 `CHART_GENERATOR` | `ChartGenerator.generate()` | 返回配置，取决于前端调用方 |

---

## 10. 作为开发者应该怎样验证

不要只测试“页面能显示结果”，建议按以下顺序验证：

```text
1. 确认后端能启动
2. 确认 /auth/login 能取得 JWT
3. 带 JWT 请求 /database/tables
4. 请求某张表的数据分页接口
5. 调用 /database/text2sql
6. 记录返回 SQL
7. 查看数据库连接日志，确认是不是 mock 分支
8. 用数据库客户端独立执行返回 SQL
9. 对比真实结果和接口结果
10. 只有在确认页面收到图表配置后，才能说图表闭环完成
```

排错时要把三个问题分开：

```text
认证失败       → Token、用户、依赖注入
SQL 生成失败    → LLM 配置、JSON 提取、Prompt
SQL 执行失败    → 数据库连接、表名、列名、SQLAlchemy
页面显示异常    → API 类型、React 状态、渲染分支
```

---

## 11. 面试回答模板

如果面试官问“你们项目如何实现自然语言数据库查询”，可以这样回答：

> 前端数据库页调用受 JWT 保护的 `/database/text2sql`。后端把固定的三张业务表 Schema、用户问题和查询意图放入 Prompt，请 LLM 返回 SQL、解释、预期列和可视化提示。服务先做 SELECT、危险关键词、注释和多语句检查，再通过 SQLAlchemy 执行；如果没有成功建立数据库 engine，当前代码会进入按 SQL 文本匹配的 mock 数据分支。接口返回 SQL、解释、数据、列名、行数和可视化提示，当前数据库页面把这些结果渲染为表格。项目另外有 SmartDataAnalyzer 和 ChartGenerator 工具，但不能仅凭它们存在就声称数据库页面已经把分析和图表完整串起来。

---

## 12. 练习

1. 为什么 `DATABASE_URL` 缺失时，`/database/text2sql` 仍可能返回成功？
2. Prompt 要求最多 100 条，为什么还不能说服务层强制限制了 100 条？
3. `validate_sql()` 为什么不能替代 SQL AST 解析和只读数据库账号？
4. 数据库页当前是否直接使用 `SmartDataAnalyzer`？请根据调用链回答。
5. `visualization_hint="line"` 返回后，当前数据库页面会自动显示折线图吗？为什么？
6. `ToolExecutor.execute_chart_generator()` 和数据库页面的 Text2SQL 结果渲染，分别处于哪条链路？
7. 如果页面显示了 mock 数据，你会检查哪些环境变量和日志？

---

## 13. 留给你的笔记区

### 13.1 我自己的调用链图

```text



```

### 13.2 我认为当前实现的一个风险

```text



```

### 13.3 我会如何改进查询安全

```text



```

