# DeepResearch 学习手册：第 88 课

## 普通聊天、长期记忆与 Text2SQL

项目中还有三类智能能力，不能和 DeepResearch 混成一条链：

```text
普通聊天：检索资料后生成流式回答
长期记忆：把过去会话压缩后按用户语义召回
Text2SQL：把自然语言转成只读 SQL 并执行
```

## 1. 普通聊天链路

主要接口：

```text
POST /chat/completion/v1
POST /chat/completion
POST /chat/completion/v3
```

它们是兼容路径，分别覆盖旧链路、政策知识库检索和附件聊天场景。

### 普通聊天 V2 的流程

```text
问题
→ 政策 Milvus 检索（可选）
→ Web 搜索（可选）
→ 结果合并
→ 重排
→ 读取会话历史
→ 可选读取长期记忆
→ LLM 流式回答
→ 保存用户消息和助手消息
```

文件：`backend/app/router/chat_router.py`、`backend/app/service/chat_service.py`

`ChatService.get_chat_completion()` 会把检索结果编号，要求模型在回答中标注来源；如果有 `session_id`，先把当前用户问题写入会话，再取历史消息加入提示词，回答结束后再保存助手消息。

## 2. 普通聊天的三种上下文

最终提示词可能包含：

```text
参考资料：本次检索得到的文档
历史对话：当前会话的短期上下文
相关历史记忆：跨会话的长期上下文
当前问题：用户现在的问题
```

这三者作用不同：

| 上下文 | 保存位置 | 作用 |
|---|---|---|
| 检索资料 | Milvus/Web 结果 | 回答当前事实问题 |
| 会话历史 | ChatMessage 或旧 Redis 会话 | 保持当前对话连续性 |
| 长期记忆 | PostgreSQL + Milvus | 跨会话记住用户偏好和主题 |

## 3. 长期记忆的写入

文件：`backend/app/service/memory_service.py`、`router/memory_router.py`

用户从一个会话创建记忆时：

```text
验证 session_id 属于当前用户
→ 读取 ChatMessage
→ LLM 生成 summary、key_insights、user_preferences、topics
→ PostgreSQL 写入 LongTermMemory
→ 对摘要、洞察和主题分别生成 Embedding
→ 写入 Milvus long_term_memories
```

PostgreSQL 的 `LongTermMemory` 保存记忆元数据、摘要、洞察、token 数和 Milvus ID；Milvus 保存可用于语义检索的向量和文本。

## 4. 长期记忆的召回

```text
当前问题
→ generate_embedding(query)
→ Milvus long_term_memories
→ expr 过滤 user_id
→ 取 top_k 相似记忆
→ 去重
→ 拼成 [相关历史记忆]
→ 放入普通聊天提示词
```

用户过滤是边界重点。没有 `user_id` 过滤，语义相似搜索可能召回其他用户的记忆。

当前聊天服务只有在拿到 `user_id` 时才构建长期记忆上下文，因此看到“记忆已经创建但回答没有使用”，要检查 user_id 是否贯通到 `get_chat_completion()`。

## 5. Text2SQL 链路

接口：`POST /database/text2sql`

```text
自然语言问题 + 查询意图
→ LLM 读取固定 Schema 定义
→ 生成 SQL、解释和可视化建议
→ validate_sql()
→ PostgreSQL 执行
→ 返回 data、columns、row_count、visualization_hint
```

支持的查询意图包括：

```text
stats、trend、comparison、detail
```

### 安全验证

`validate_sql()` 当前检查：

- SQL 非空。
- 必须以 `SELECT` 开头。
- 禁止 `DROP`、`DELETE`、`UPDATE`、`INSERT` 等关键词。
- 不允许多条语句。
- 不允许 SQL 注释。

这是只读防线，但仍然需要在数据库账号权限层设置只读权限；不能只依赖字符串过滤。

### 数据库不可用时

如果没有初始化 `db_engine`，当前服务可能返回 `_get_mock_data()` 的演示数据。因此接口返回成功不一定证明真实 PostgreSQL 已经连接；要看数据库连接配置和运行日志。

## 6. Text2SQL 和 CodeWizard 的相同点与不同点

| 维度 | Text2SQL | CodeWizard |
|---|---|---|
| LLM 输出 | SQL | Python |
| 执行环境 | PostgreSQL | 应用进程内受限 `exec()` |
| 主要安全边界 | SELECT 校验和数据库权限 | 正则、受限 builtins、白名单导入 |
| 结果 | 行、列、行数、可视化建议 | stdout、错误、PNG、执行记录 |
| 主要用途 | 查询结构化业务数据 | 数据清洗、统计和绘图 |

二者都遵循：

```text
LLM 负责生成执行计划
程序负责校验、执行和格式化结果
```

## 7. 常见排错判断

### 普通聊天没有引用

检查检索是否返回、重排后的字段是否包含 `content_with_weight`、提示词是否要求引用。

### 长期记忆没有生效

检查记忆是否成功写入 PostgreSQL 和 Milvus、查询 Embedding 是否成功、user_id 过滤是否匹配、聊天服务是否收到 user_id。

### Text2SQL 返回成功但数据不对

检查 LLM 生成的 SQL、Schema 是否与真实表结构一致、是否命中了 mock 数据、`visualization_hint` 是否只是建议而非真实图表。

## 8. 本课练习

请比较：

1. 短期会话历史和长期记忆分别解决什么问题？
2. 为什么 Text2SQL 返回 `success=true` 不能单独证明真实数据库已经被查询？
3. CodeWizard 和 Text2SQL 为什么都必须让程序校验 LLM 输出？
