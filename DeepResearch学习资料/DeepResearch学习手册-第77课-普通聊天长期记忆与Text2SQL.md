# DeepResearch 学习手册：第 77 课

## 普通聊天、长期记忆与 Text2SQL

DeepResearch 项目不只有一条智能问答链。除了多 Agent 研究，还保留了三条独立但互相配合的能力：

```text
普通聊天：检索资料后直接回答
长期记忆：把长对话压缩成可召回记忆
Text2SQL：把自然语言转成只读 SQL
```

## 1. 普通聊天和 DeepResearch 的区别

普通聊天的典型链路是：

```text
问题
→ 本地知识库检索
→ Web 搜索（可选）
→ 结果合并
→ 重排
→ 读取短期会话历史
→ LLM 流式回答
```

DeepResearch 的链路是：

```text
问题
→ 规划
→ 多轮搜索
→ 事实整理
→ 数据分析
→ 代码执行
→ 写作
→ 审核
```

因此普通聊天追求快速回答，DeepResearch 追求多阶段研究过程和可追踪产物。

## 2. 项目中的聊天接口路径

后端保留了多条接口：

```text
POST /chat/completion/v1
POST /chat/completion
POST /chat/completion/v3
```

### v1

大致使用：

```text
旧文档服务知识库
→ Web 搜索
→ 合并
→ DashScope 重排
→ ChatService 生成回答
```

### v2

使用 `retrieve_content()` 查询：

```text
policy_documents
```

然后再和 Web 搜索结果合并、重排、生成回答。

### v3

在 v2 的基础上增加附件：

```text
附件 ID
→ PostgreSQL ChatAttachment
→ 读取 completed 的 content_text
→ 拼接到增强问题
→ 检索和回答
```

## 3. 普通聊天的检索和重排

普通聊天并不是把所有搜索结果直接交给 LLM。它大致做：

```text
知识库结果 + Web 结果
→ rerank_documents()
→ 按相关性重新排序
→ 组成提示词
→ LLM 流式回答
```

这样可以减少无关内容进入上下文，也让来源顺序更合理。

如果检索失败，部分服务会捕获异常并返回空列表。于是页面可能仍然能显示一个答案，但这不代表知识库真的可用。

## 4. 长期记忆解决什么问题

短期会话历史不能无限增长。长期记忆服务的目标是：

```text
很多条历史消息
→ 摘要、洞察、偏好、主题
→ PostgreSQL 保存结构化记忆
→ Milvus 保存记忆向量
→ 新问题按语义召回相关记忆
```

项目中有一个估算阈值：当消息总 token 超过阈值时，可以考虑压缩记忆。

## 5. 创建长期记忆的过程

`MemoryService.create_memory()` 的步骤是：

```text
读取会话消息
→ LLM 总结对话
→ 产生 summary/key_insights/user_preferences/topics
→ 创建 LongTermMemory 数据库记录
→ 为摘要、洞察和主题生成向量
→ 写入 long_term_memories 集合
→ 保存 Milvus ID
```

数据库记录适合管理：

```text
用户 ID
会话 ID
摘要
关键洞察 JSON
token 数
创建时间
```

Milvus 适合做：

```text
给定新问题，找语义上最相关的历史记忆
```

## 6. 长期记忆如何防止串用户

向量召回时会使用用户过滤条件：

```text
user_id == 当前用户 ID
```

这很重要，因为向量相似度本身只判断“内容像不像”，不会自动判断“是不是这个用户的”。

用户隔离必须由查询过滤和后端授权共同保证。

## 7. 长期记忆如何进入聊天上下文

`build_memory_context()` 会把召回结果格式化成提示词上下文，例如：

```text
相关历史记忆：
- 用户关注智慧交通和行业研究
- 用户偏好详细、通俗的解释
- 之前讨论过 Milvus 集合命名
```

然后 `ChatService.get_chat_completion()` 把它和：

```text
会话历史
检索文档
当前问题
```

一起交给 LLM。

## 8. Text2SQL 解决什么问题

Text2SQL 允许用户直接问：

```text
2024 年智慧交通市场规模是多少？
各企业 2024 年营收怎么比较？
2023 到 2025 年市场规模趋势如何？
```

系统把问题转换成 SQL，再执行查询并返回：

```text
SQL
解释
行数据
列名
可视化建议
置信度
```

## 9. Text2SQL 的执行链

```text
自然语言问题
→ 读取预设 Schema
→ LLM 生成 JSON
→ 提取 sql
→ validate_sql()
→ 执行 SELECT
→ 格式化数据
→ 返回 visualization_hint
```

预设 Schema 中包括：

```text
industry_stats
company_data
policy_data
```

模型并不是自动读取整个数据库结构，而是根据提示词中的 Schema 生成 SQL。

## 10. Text2SQL 的安全校验

服务会拒绝明显的写操作和危险关键词：

```text
DROP
DELETE
UPDATE
INSERT
TRUNCATE
ALTER
CREATE
GRANT
EXEC
注释符号
```

同时要求：

```text
SQL 必须以 SELECT 开头
不允许多条语句
```

但要准确理解：这仍然是字符串级校验，不是完整 SQL 安全证明。生产环境还应使用只读数据库账号、SQL 解析器、表/列白名单、超时和行数限制。

## 11. 数据库不可用时的边界

Text2SQL 的 `execute_sql()` 在数据库连接不可用时可能进入 mock 数据路径。

所以看到接口返回：

```text
success = true
data 有内容
```

还要确认：

```text
数据来自真实 PostgreSQL
还是服务内置的 mock 数据
```

这和前端 Mock SSE 的证据边界类似：页面有结果，不等于真实数据源已连接。

## 12. Text2SQL 和 CodeWizard 的区别

| 能力 | Text2SQL | CodeWizard |
|---|---|---|
| 输入 | 自然语言查询 | 研究数据和分析任务 |
| LLM 输出 | SQL | Python |
| 执行对象 | 数据库 | Python 运行环境 |
| 主要结果 | 表格数据 | 计算结果和图片 |
| 安全重点 | 只读 SQL、数据库权限 | 沙箱、资源和代码权限 |
| 可视化 | `visualization_hint` | ECharts/PNG 图表 |

两者都属于“LLM 生成可执行程序”，但执行环境不同。

## 13. 三条链路如何组合

普通聊天可以使用长期记忆和检索内容：

```text
短期会话 + 长期记忆 + RAG 文档 + 当前问题
→ ChatService
→ LLM 回答
```

数据库页面可以使用 Text2SQL：

```text
用户问题
→ Text2SQL
→ PostgreSQL
→ 表格/图表
```

DeepResearch 也可以通过自己的 Agent 或工具使用搜索、知识库、数据分析，但它的主流程仍然是 V2 多阶段 Agent 编排。

## 14. 排错练习

### 普通聊天能回答，但引用为空

检查：

```text
检索结果是否为空
rerank 是否返回内容
SSE 是否发送 references/source 事件
前端是否保存 search_results
```

### 长期记忆创建成功，但搜索不到

检查：

```text
PostgreSQL LongTermMemory 是否创建
Milvus 集合是否存在
摘要/洞察是否生成向量
查询向量维度是否一致
user_id 过滤是否匹配
```

### Text2SQL 返回成功但数据可疑

检查：

```text
生成的 SQL
真实数据库连接
是否进入 _get_mock_data()
Schema 和真实表是否一致
```

## 15. 本课练习

1. 普通聊天和 DeepResearch 的核心差异是什么？
2. 长期记忆为什么同时需要 PostgreSQL 和 Milvus？
3. 为什么向量搜索必须按 `user_id` 过滤？
4. Text2SQL 为什么不能只相信 LLM 生成的 SQL？
5. Text2SQL 和 CodeWizard 都生成可执行代码，它们的执行环境有什么不同？

