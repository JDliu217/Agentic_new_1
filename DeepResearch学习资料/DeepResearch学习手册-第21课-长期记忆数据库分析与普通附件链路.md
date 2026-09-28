# DeepResearch 学习手册·第 21 课

## 长期记忆、数据库分析与普通附件链路

> 本课依据本地项目 `D:\课\s4-6\industry_information_assistant\frontend` 与 `backend` 源码整理。三个功能都涉及“用户输入 → 后端处理 → 页面展示”，但它们的数据用途完全不同：长期记忆保存用户历史，数据库页查询结构化行业数据，普通附件服务当前会话中的文件问答。

---

## 1. 三条链路先分开

```text
长期记忆：会话消息 → LLM 总结 → PostgreSQL 记忆记录 + Milvus 记忆向量

数据库分析：自然语言问题 → LLM 生成 SELECT → SQL 校验 → PostgreSQL 或 mock 数据 → 表格

普通附件：文件 → ChatAttachment 记录 → 后台提取文本 → /chat/completion/v3 → SSE 回复
```

不要把下面三个概念混为一谈：

| 功能 | 核心对象 | 主要用途 |
|---|---|---|
| 知识库 | `KnowledgeBase`、`Document`、文档切片 | 用户主动上传资料，供检索和研究使用 |
| 长期记忆 | `LongTermMemory`、记忆向量 | 保存用户过去对话中的摘要、洞察和主题 |
| 普通附件 | `ChatAttachment` | 当前聊天临时引用文件 |

---

## 2. 长期记忆页面和 API

文件：

```text
frontend/src/pages/memory/index.tsx
frontend/src/api/memory.ts
backend/app/router/memory_router.py
backend/app/service/memory_service.py
```

前端调用的接口包括：

```http
GET  /memories
GET  /memories/{memory_id}
POST /memories/search
POST /memories/create
DELETE /memories/{memory_id}
GET  /memories/context/{query}
```

进入记忆页面后，前端请求最多 50 条记忆，显示摘要、token 数、关键洞察和创建时间。搜索框调用 `/memories/search`，返回结果包含相似度分数和记忆类型。

当前导航中的“记忆库”入口仍可能显示“暂未开放”，但路由和页面源码已经存在；因此要区分“代码存在”和“用户从导航可以正常进入”这两个事实。

---

## 3. 从会话创建一条长期记忆

### 3.1 后端校验

`POST /memories/create` 接收 `session_id`，后端依次检查：

1. `session_id` 是否是合法 UUID。
2. 会话是否存在且属于当前用户。
3. 会话是否有消息。

然后按时间顺序读取 `ChatMessage`。

### 3.2 LLM 总结

`MemoryService.create_memory()` 调用 `summarize_conversation(messages)`，让 LLM 生成结构化内容，主要包括：

```text
summary
key_insights
user_preferences
topics
```

如果 LLM 返回 JSON 解析失败，服务会返回默认结构，例如“对话包含 N 条消息”。这保证接口有结果，但也可能隐藏模型输出质量问题，日志仍需要检查。

### 3.3 PostgreSQL 记录

服务计算每条消息的估算 token 数，然后创建 `LongTermMemory`：

```text
user_id
session_id
summary
key_insights
token_count
created_at
```

数据库记录先提交，再继续处理向量。这意味着数据库记忆可能已经创建，而向量写入随后失败。

### 3.4 Milvus 记忆向量

服务会分别为以下内容生成向量：

- 摘要：`memory_type = summary`
- 关键洞察：`memory_type = insight`
- 主题集合：`memory_type = topics`

每个向量记录包含：

```text
id
user_id
session_id
memory_type
content
metadata
vector
```

生成的 Milvus ID 会写回 `LongTermMemory.milvus_ids`。这样删除数据库记忆时，可以根据 ID 删除对应向量。

---

## 4. 记忆检索和上下文构建

### 4.1 语义搜索

`retrieve_memories()` 的流程是：

```text
查询文本
  → generate_embedding(query)
  → Memory collection 的 COSINE 搜索
  → expr 过滤 user_id
  → 返回 top_k
```

按 `user_id` 过滤是关键的多租户边界，否则不同用户的历史记忆可能互相泄露。

### 4.2 上下文

`build_memory_context()` 先检索最多 3 条记忆，再按内容去重，拼成：

```text
[相关历史记忆]
- 历史对话摘要: ...
- 相关知识点: ...
- 用户关注的主题: ...
```

这个字符串可以作为当前问题的额外上下文传给聊天模型。

### 4.3 当前接通边界

源码中普通聊天 Router 调用 `get_chat_completion()` 时，没有明确把 `user_id` 传入长期记忆上下文路径。因此不能简单宣称“用户每次普通聊天都会自动带上长期记忆”。当前能确认的是：

```text
记忆创建接口存在
记忆搜索接口存在
记忆上下文服务存在
普通聊天自动注入是否完全接通，需要继续追踪实际调用参数
```

这是面试中应主动说明的实现边界。

---

## 5. 记忆删除的双写问题

删除记忆时，服务先根据 `memory_id` 和 `user_id` 找到 PostgreSQL 记录，然后尝试：

```text
遍历 memory.milvus_ids
  → collection.delete(id == ...)
删除 PostgreSQL LongTermMemory
```

Milvus 删除异常会被记录，但数据库删除仍可能继续。于是可能出现：

```text
页面看不到记忆
但向量库残留旧向量
```

生产系统需要事务补偿、删除任务重试或定期一致性清理。

---

## 6. 数据库页面：结构化数据浏览

文件：

```text
frontend/src/pages/database/index.tsx
frontend/src/api/database.ts
backend/app/router/database_router.py
backend/app/service/text2sql_service.py
```

页面只展示白名单表：

```text
industry_stats
company_data
policy_data
```

页面加载时：

```text
GET /database/tables
  → 过滤 ALLOWED_TABLES
  → 选择第一张表
  → GET /database/tables/{table}/data
```

用户切换表或分页时，再请求对应表数据。前端维护：

```text
tables
selectedTable
tableData
tableColumns
pagination
```

这条路径是“表浏览”，不涉及 LLM。

---

## 7. Text2SQL 自然语言查询

用户在数据库页输入问题，例如“智慧交通市场规模是多少”，前端调用：

```http
POST /database/text2sql
```

请求体：

```json
{
  "question": "智慧交通市场规模是多少",
  "intent": "stats"
}
```

### 7.1 服务初始化

后端从环境变量构造数据库连接：

```text
DATABASE_URL
或 POSTGRES_HOST、POSTGRES_PORT、POSTGRES_USER、POSTGRES_PASSWORD、POSTGRES_DB
```

然后初始化 `Text2SQLService`，使用配置中的 LLM API 和 `qwen-plus`。

### 7.2 LLM 生成 SQL

Prompt 包含允许查询的表结构和字段说明，要求模型返回：

```json
{
  "sql": "SELECT ...",
  "explanation": "...",
  "expected_columns": ["..."],
  "visualization_hint": "line/bar/pie/table/none",
  "confidence": 0.95
}
```

服务支持从纯 JSON、Markdown 代码块或文本中的 JSON 对象提取结果。

### 7.3 SQL 安全校验

`validate_sql()` 检查：

```text
SQL 非空
以 SELECT 开头
不包含 UPDATE、DELETE、INSERT、DROP 等禁止关键词
不包含多条语句
不包含 -- 或 /* 注释
```

这是应用层的第一道防线。生产环境还应使用只读数据库账号、SQL 解析器、表和列白名单、超时和资源限制，不能只依赖字符串检查。

### 7.4 执行或 mock

`execute_sql()` 在有数据库连接时使用 SQLAlchemy 执行查询；如果 `db_engine` 不存在，当前代码可能调用 `_get_mock_data(sql)` 返回演示数据。

因此页面成功显示一组结果，不一定证明真实 PostgreSQL 已被查询。要判断是真实数据还是 mock，必须检查配置、服务日志和执行路径。

### 7.5 前端结果展示

数据库页面显示：

```text
生成的 SQL
解释说明
结果列和行
行数
错误信息
```

当前页面主要渲染表格，没有根据 `visualization_hint` 自动调用 ECharts。后端返回可视化建议不等于前端已经完成图表展示。

---

## 8. 普通聊天附件链路

普通聊天附件使用另一套对象和接口：

```text
frontend/src/components/sender/index.tsx
frontend/src/pages/chat/newchat.tsx
frontend/src/pages/chat/index.tsx
frontend/src/api/session.ts
backend/app/router/attachment_router.py
```

### 8.1 选择和上传

`ComSender` 使用隐藏的 `<input type="file">`。上传完成后，附件显示为：

```text
uploading → pending → processing → completed / failed
```

页面先生成临时 ID，上传成功后替换成后端真实附件 ID。附件状态为 completed 时，发送消息才会把 ID 放进 `attachment_ids`。

### 8.2 上传接口

```http
POST /attachments
Content-Type: multipart/form-data
```

表单字段是：

```text
file
session_id
```

后端验证会话和扩展名，把文件保存到 `/tmp/chat_attachments`，创建 `ChatAttachment` 记录，然后通过 `BackgroundTasks` 调用 `process_attachment()`。

### 8.3 附件处理的真实能力

当前 `process_attachment()` 对文本类文件会直接读取文本：

```text
txt、md、py、js、ts、json、yaml、xml、csv、html
```

但以下类型目前主要写入占位文本：

```text
PDF： [PDF 文件: 文件名]
Word： [Word 文档: 文件名]
图片： [图片: 文件名]
```

因此普通附件链不能和知识库上传的 DocMind 链混为一谈。知识库文档会解析、切片、向量化；普通附件当前主要是会话级内容提取和引用。

### 8.4 发送到聊天接口

如果有已完成附件，聊天页调用：

```http
POST /chat/completion/v3
```

请求体包含：

```json
{
  "session_id": "...",
  "question": "请分析附件",
  "attachment_ids": ["..."]
}
```

没有附件时走 `/chat/completion`；DeepResearch 模式走 `/research/stream`。这三条接口不能只根据“都是聊天”就当成同一条业务链。

---

## 9. 三种数据分析能力的边界

项目中可能出现三个看起来相似的词：

```text
知识库检索：从文档切片中找相关内容
Text2SQL：从关系数据库中生成并执行 SELECT
CodeWizard：让 Python 对结构化数据做计算和图表
```

可以按数据形态区分：

| 能力 | 输入 | 输出 | 典型问题 |
|---|---|---|---|
| RAG | 文本、文档切片 | 引用片段 | “政策中如何定义车路协同？” |
| Text2SQL | 表结构和自然语言 | SQL、行列数据 | “2024 年市场规模是多少？” |
| CodeWizard | 数据和分析任务 | 计算结果、图表 | “比较三年趋势并画图” |

DeepResearch 可能把它们串起来，但每个服务的职责仍然不同。

---

## 10. 练习

1. 为什么记忆列表可以从 PostgreSQL 读取，而记忆搜索要查询 Milvus？
2. 如果记忆向量写入失败，数据库中的记忆记录会怎样？
3. 为什么 Text2SQL 结果显示成功不一定代表查到了真实数据库？
4. 列出 `validate_sql()` 的限制，并提出两种更可靠的生产防护。
5. 普通附件和知识库文档上传分别走哪些接口？
6. 为什么 PDF 普通附件当前不能宣称已经完成文本解析？
7. 用户上传附件但状态仍 processing 时，发送按钮为什么只传 completed 的附件 ID？
8. 将“政策解释”“市场规模统计”“趋势图表”分别分配给 RAG、Text2SQL、CodeWizard，并说明理由。

---

## 11. 面试官追问

1. 长期记忆为什么要同时落 PostgreSQL 和 Milvus？
2. 记忆检索中的 `user_id` 过滤解决什么问题？
3. 如何保证删除数据库记忆时不会残留向量？
4. Text2SQL 如何防止模型生成破坏性 SQL？字符串检查够不够？
5. 为什么要限制数据库页展示的表？
6. mock 数据会给测试和生产判断带来什么风险？
7. 普通附件链和知识库链为什么不能共用“上传成功”的判断？
8. 如果要支持真正的 PDF、Word 和图片理解，你会把能力放在哪一层？
9. DeepResearch 什么时候应该使用 RAG，什么时候应该使用 Text2SQL？
10. 如何让普通聊天真正接通长期记忆并保持用户隔离？

---

## 12. 本课结论

```text
长期记忆：保存和召回用户历史
数据库页：浏览和查询结构化行业数据
普通附件：为当前会话提供文件引用
```

理解这三条路径后，你可以解释为什么项目同时使用 PostgreSQL、Milvus、LLM、SSE 和文件后台任务，而不会把所有功能都笼统称为“AI 搜索”。

---

## 13. 留白与我的笔记

### 13.1 我画的三条链路

<!-- 分别画长期记忆、Text2SQL、普通附件从页面到后端再到结果的箭头。 -->



### 13.2 我需要验证的 mock 或占位路径

<!-- 记录数据库不可用时的 mock 数据、PDF/Word/图片附件的占位文本及对应日志。 -->



### 13.3 我认为最重要的安全边界

<!-- 记录 user_id 过滤、SQL 只读校验、附件权限和服务端认证。 -->



### 13.4 面试回答草稿

<!-- 用自己的话回答本课第 11 节问题。 -->



