# DeepResearch 学习手册·第 59 课

## Text2SQL：从自然语言到只读查询

这一课回答一个核心问题：用户说“查询 2024 年行业规模”，系统怎样把它变成数据库结果？

```text
用户问题
  ↓
前端 POST /database/text2sql
  ↓
FastAPI database_router
  ↓
Text2SQLService.generate_sql
  ↓
LLM 根据 Schema 生成 JSON 和 SELECT
  ↓
validate_sql 安全校验
  ↓
SQLAlchemy 执行，或无数据库时返回 mock 数据
  ↓
数据、列名、解释、可视化建议
  ↓
React 数据库页面展示
```

---

## 1. 前端入口和请求契约

文件：`frontend/src/api/database.ts`。

前端函数为：

```ts
text2sql(question, intent = 'stats')
```

它向 `/database/text2sql` 发送：

```json
{
  "question": "2024 年行业市场规模是多少？",
  "intent": "stats"
}
```

`intent` 有四种主要值：

- `stats`：统计
- `trend`：趋势
- `comparison`：对比
- `detail`：明细

前端响应类型包含：`success`、`sql`、`explanation`、`data`、`columns`、`visualization_hint`、`confidence`、`row_count` 和 `error`。

这说明页面不只显示最终数字，也可以把生成的 SQL 和解释展示出来，便于用户检查。

---

## 2. Router 做了什么

文件：`backend/app/router/database_router.py`。

`POST /database/text2sql` 使用 `get_current_user_required`，所以未登录请求不会进入 Text2SQL 服务。

路由读取 LLM 配置，并从 `DATABASE_URL` 或 PostgreSQL 分项环境变量构建连接字符串。然后创建：

```python
Text2SQLService(
    llm_api_key=config.api_key,
    llm_base_url=config.base_url,
    db_connection_string=db_url if db_url else None,
    model="qwen-plus"
)
```

最后调用：

```python
result = await service.query(request.question, request.intent)
```

这里的 Router 主要负责认证、配置和请求转换；自然语言理解、校验和执行都在 Service 中。

---

## 3. LLM 负责生成什么

文件：`backend/app/service/text2sql_service.py`。

服务把固定的 `SCHEMA_DEFINITION` 放进 Prompt。Schema 当前描述了 `industry_stats`、`company_data` 和 `policy_data` 等表及字段。

LLM 被要求返回结构化 JSON：

```json
{
  "sql": "SELECT ...",
  "explanation": "查询说明",
  "expected_columns": ["year", "metric_value"],
  "visualization_hint": "line",
  "confidence": 0.95
}
```

因此 LLM 的作用是：

1. 理解用户问题。
2. 根据提供的 Schema 选择表和字段。
3. 生成 SQL。
4. 解释 SQL。
5. 推荐结果适合用折线图、柱状图还是表格展示。

LLM 本身没有读取数据库，也没有凭空获得数据库真实结果。它只生成候选查询；真实结果要由后面的执行环境产生。

---

## 4. 为什么还需要执行环境

`Text2SQLService.query` 的顺序是：

```text
generate_sql
  → validate_sql
  → execute_sql
  → 组装响应
```

`execute_sql` 在存在数据库连接时通过 SQLAlchemy 建立连接并执行查询：

```python
with self.db_engine.connect() as conn:
    result = conn.execute(text(sql))
```

这一步才真正接触 PostgreSQL。数据库是否可用、账号权限、连接池、表是否存在、查询是否超时，都属于执行环境问题，不是 LLM 能力本身。

如果没有数据库连接，当前代码会调用 `_get_mock_data`，根据 SQL 中的表名返回演示数据。这能帮助前端演示，但不能证明真实数据库链路已经成功。

---

## 5. 当前代码的 SQL 安全校验

`validate_sql` 当前会检查：

- SQL 不能为空。
- 必须以 `SELECT` 开头。
- 禁止 `DROP`、`DELETE`、`UPDATE`、`INSERT`、`TRUNCATE` 等关键词。
- 不允许多条语句。
- 不允许 SQL 注释。

这是一个基础的黑名单校验，能拦截很多明显的写操作，但不能等同于生产级 SQL 安全方案。原因是字符串检查容易受大小写、注释、语法变体、函数和资源消耗影响。

生产环境还应增加：

1. 使用只读数据库账号。
2. 通过 SQL AST 解析器检查语句结构。
3. 限制可访问的表和字段。
4. 强制最大返回行数和查询超时。
5. 限制数据库网络权限。
6. 记录 SQL、用户、耗时和错误。

---

## 6. 它和 Agent 工具调用的关系

旧的 ReAct 体系在 `react_controller.py` 中注册了 `text2sql` 工具；`tool_executor.py` 中的 `execute_text2sql` 再调用 `Text2SQLService.query`。

所以可以把它理解为两层：

```text
Agent 决策层：判断要不要调用 text2sql，以及传什么问题和意图
        ↓
Text2SQL 执行层：生成 SQL、校验 SQL、执行 SQL、返回结构化结果
```

Agent 不应该直接把自然语言拼成 SQL 并执行。工具服务必须保留自己的校验和权限边界，因为工具也可能被错误的模型输出调用。

---

## 7. 本课最重要的结论

Text2SQL 的能力由多个部分共同决定：

```text
LLM：理解问题和生成候选 SQL
Schema：告诉 LLM 数据库有哪些表和字段
执行环境：连接数据库并返回真实结果
安全层：限制 SQL 能做什么
前端：展示结果、SQL、解释和图表建议
```

如果 LLM 很强但 Schema 错了，SQL 仍可能错误；如果 SQL 正确但数据库没有连接，只会得到 mock 数据；如果数据库权限过大，单靠 Prompt 不能保证安全。

---

## 8. 源码确认与运行验证的边界

本课中的调用顺序和字段来自源码阅读。当前项目已确认 Python 可以通过编译检查，但真实 PostgreSQL、LLM 和 Text2SQL 端到端执行仍需要对应服务、环境变量和数据表，因此不能仅凭源码断言真实查询已经成功。

---

## 练习

用户问：“比较 2023 和 2024 年智慧交通市场规模，并画趋势图。”

请判断：

1. `intent` 更适合填什么？
2. 哪一步由 LLM 完成？
3. 哪一步必须依赖 PostgreSQL？
4. 如果没有数据库连接，当前项目会发生什么？

参考答案：`trend`；LLM 生成 SQL 和可视化建议；SQLAlchemy 执行查询依赖 PostgreSQL；当前代码会回退到模拟数据，所以页面可能有结果，但不能证明真实数据查询成功。

