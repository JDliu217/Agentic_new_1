# DeepResearch 学习手册·第 112 课：普通聊天、附件、长期记忆与 Text2SQL 边界

## 1. 先看总对照

| 模块 | 输入 | 主要存储/数据源 | 主要处理 | 输出 |
|---|---|---|---|---|
| 普通聊天 | 用户问题、会话 ID | 旧文档服务/政策 Milvus/网页、会话历史 | 检索、重排、LLM 流式回答 | SSE 消息和引用 |
| 普通附件 | 文件、会话 ID、问题 | `ChatAttachment`、`content_text` | 后台提取文本，拼入问题 | SSE 回答 |
| 长期记忆 | 会话消息 | PostgreSQL + `long_term_memories` Milvus | LLM 总结、向量召回 | 记忆列表或上下文 |
| Text2SQL | 自然语言问题、查询意图 | PostgreSQL 业务表或 mock 数据 | LLM 生成 SELECT、校验、执行 | 结构化数据和图表提示 |
| DeepResearch | 研究问题、搜索模式 | `ResearchState`、检查点、网络/本地检索 | 六个 Agent 协作 | 研究步骤、图表、报告 |

这些模块都可能使用 LLM 或向量，但它们的输入、存储和结果契约不同。

## 2. 普通聊天：检索后再生成

### 2.1 V1 `/chat/completion/v1`

文件：`backend/app/router/chat_router.py:59-127`

真实流程：

```text
验证/创建旧会话
→ 按开关检索旧知识库
→ 按开关进行网页搜索
→ 合并文档
→ DashScope 重排
→ ChatService.get_chat_completion()
→ SSE 流式返回
```

`ChatService.rerank_documents()` 会更新相关度、重新排序，并限制最多 10 个文档和最大 token 数。然后 `get_chat_completion()` 将参考内容、短期历史和问题放入 Prompt，调用 LLM 流式输出。

### 2.2 V2 `/chat/completion`

文件：`chat_router.py:129-209`

知识库检索改为 `retrieve_content(indexNames="policy_documents")`，再和网页结果合并、重排。这里的 `policy_documents` 是政策检索链，不等同于新知识库上传链的 `kb_<知识库名称>`。

### 2.3 普通聊天的事件

`ChatService.get_chat_completion()` 会发送：

```text
event: message\ndata: {"role":"assistant","content":"..."}\n\n
event: message\ndata: {"documents":[...]}\n\n
event: end\ndata: [DONE]\n\n
```

它与 V2 DeepResearch 的 `research_step`、`research_complete` 事件不是同一套前端契约。

## 3. 普通附件：临时上下文，不是知识库

### 3.1 上传和处理

文件：`backend/app/router/attachment_router.py:55-187`

```text
POST /attachments
→ ChatAttachment(status=pending)
→ BackgroundTasks
→ status=processing
→ 提取 content_text
→ status=completed
```

文本文件直接读取；PDF、Word 和图片当前保存的是类似 `[PDF 文件: xxx]` 的占位文本，并没有走知识库的 DocMind 解析、切片和 Milvus 写入。

### 3.2 带附件聊天

文件：`backend/app/router/chat_router.py:212-314`

接口先读取已完成附件的 `content_text`，每个附件最多取 10000 个字符，拼接为：

```text
用户问题 + 上传的附件内容
→ ChatService.get_chat_completion()
```

这是一种“当前请求上下文增强”。文件不会自动成为可供后续问题搜索的长期知识库。

### 3.3 授权边界

上传接口使用可选认证 `get_current_user`，并检查会话是否存在，但部分详情、列表和删除查询主要按附件 ID 或 session ID 查找，不能简单视为完整的用户隔离。学习时应区分“保存了 user_id”与“每个读写路径都强制过滤 user_id”。

## 4. 长期记忆：把对话压缩成可召回知识

### 4.1 创建记忆

文件：`backend/app/router/memory_router.py:157-218`、`backend/app/service/memory_service.py:180-221`

创建流程：

```text
验证 ChatSession 属于当前用户
→ 读取 ChatMessage
→ LLM 总结 summary、key_insights、topics、preferences
→ PostgreSQL LongTermMemory
→ 摘要/洞察/主题分别生成向量
→ Milvus long_term_memories 集合
```

PostgreSQL 保存可管理的记忆元数据，Milvus 保存语义搜索所需的向量和内容，两者通过 `milvus_ids` 关联。

### 4.2 召回记忆

文件：`memory_service.py:313-377`

```text
当前问题
→ generate_embedding(query)
→ Milvus long_term_memories
→ expr: user_id == 当前用户
→ COSINE top_k
→ 返回摘要/洞察/主题
```

用户过滤发生在向量查询表达式中；这与知识库按集合或 `kb_id` 过滤是不同实现。

### 4.3 一个必须发现的边界

`ChatService.get_chat_completion()` 支持 `user_id` 参数，并且有构造记忆上下文的代码；但当前聊天路由调用它时没有从认证依赖传入 `user_id`。所以“长期记忆 API 能搜索”可以由源码证明，“每次普通聊天都会自动注入当前用户长期记忆”不能由当前调用链证明。

## 5. Text2SQL：自然语言到只读数据库查询

### 5.1 请求入口

文件：`backend/app/router/database_router.py:203-257`

```text
POST /database/text2sql
{
  "question": "近几年行业市场规模趋势如何？",
  "intent": "trend"
}
```

路由读取 LLM 配置和 PostgreSQL 环境变量，创建 `Text2SQLService`，调用 `query()`，然后返回 SQL、解释、数据、列名、可视化提示和置信度。

### 5.2 LLM 生成格式

`Text2SQLService.generate_sql()` 要求 LLM 返回 JSON：

```json
{
  "sql": "SELECT ...",
  "explanation": "...",
  "expected_columns": ["year", "metric_value"],
  "visualization_hint": "line",
  "confidence": 0.95
}
```

LLM 负责提出查询，不能直接代表查询已经安全或已经执行。

### 5.3 SQL 校验

文件：`text2sql_service.py:210-242`

当前校验包括：

```text
非空
→ 禁止 DROP/DELETE/UPDATE/INSERT 等关键词
→ 必须以 SELECT 开头
→ 禁止多条语句
→ 禁止注释
```

这是字符串级规则，不是完整 SQL 解析器，也不是数据库权限隔离。生产环境还应使用只读数据库用户、SQL AST 校验、超时、资源限制和允许表白名单。

### 5.4 真实数据库与 mock 分支

`execute_sql()` 在有 `db_engine` 时执行 PostgreSQL；没有数据库连接时调用 `_get_mock_data()`。因此页面可能展示看似合理的数据，但它可能来自代码中的演示数据，而非真实数据库。

判断结果是否真实时，要查看：

```text
数据库连接字符串
db_engine 是否成功初始化
返回的 SQL 和日志
是否出现 mock 分支
```

## 6. 四条链的关键区别

```text
普通聊天：当前问题 + 检索结果 + 短期历史 → LLM
普通附件：当前文件文本直接拼入当前问题 → LLM
长期记忆：历史对话总结并向量化 → 按用户召回 → 可作为上下文
Text2SQL：自然语言 → SQL → 安全校验 → 数据库/Mock
DeepResearch：问题 → ResearchState → 六个 Agent → 报告
```

不要因为它们都“用了 LLM”就把它们理解为同一功能。

## 7. 练习

1. 普通附件为什么不会自动出现在新知识库的 Milvus 检索结果中？
2. 长期记忆为什么同时需要 PostgreSQL 和 Milvus？
3. 为什么 `ChatService.get_chat_completion()` 支持长期记忆，不代表普通聊天已经自动使用长期记忆？
4. Text2SQL 中 LLM、`validate_sql()`、`execute_sql()` 和 `_get_mock_data()` 各自负责什么？
5. 给出一个例子，说明“接口返回成功”但结果仍可能不是生产真实数据。

