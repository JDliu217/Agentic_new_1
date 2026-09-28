# DeepResearch 学习手册·第 58 课

## 长期记忆：从会话摘要到语义召回

长期记忆解决的问题是：

> 当前聊天窗口之外，系统怎样保留用户长期关心的主题、偏好和重要结论？

它不是简单地把所有历史消息原样塞进每个 Prompt，而是先总结，再向量化，最后按当前问题召回相关记忆。

---

## 1. 长期记忆的完整链路

~~~~text
ChatSession + ChatMessage
  ↓
POST /memories/create
  ↓
LLM 总结 summary、key_insights、topics、user_preferences
  ↓
PostgreSQL LongTermMemory
  ↓
Embedding
  ↓
Milvus long_term_memories
  ↓
用户查询
  ↓
查询向量 + user_id 过滤
  ↓
召回最多若干条记忆
  ↓
build_memory_context
  ↓
加入聊天 Prompt
~~~~

PostgreSQL 保存记忆的业务元数据；Milvus 保存可语义搜索的向量和文本。

---

## 2. 如何从会话创建记忆

接口：POST /memories/create。

后端会：

1. 验证 session_id 格式。
2. 验证会话属于当前用户。
3. 读取该会话的 ChatMessage。
4. 没有消息时拒绝创建。
5. 调用 MemoryService.create_memory。

这说明记忆不能从任意会话 ID 创建。会话归属检查先于总结和向量化。

---

## 3. LLM 总结输出什么

MemoryService.summarize_conversation 会把消息拼成：

~~~~text
用户: ...
助手: ...
~~~~

然后让模型返回 JSON，主要字段包括：

- summary：两三句话的对话摘要。
- key_insights：关键知识点。
- user_preferences：兴趣、沟通风格和关注领域。
- topics：主题标签。

如果 LLM 调用或 JSON 解析失败，服务会返回一个默认摘要结构，而不是直接让整个请求崩溃。

这是一种降级策略，但也可能产生“记忆创建成功、内容质量很低”的情况。

---

## 4. PostgreSQL 中的 LongTermMemory

模型字段包括：

- user_id
- session_id
- summary
- key_insights
- milvus_ids
- token_count
- created_at

create_memory 先写数据库：

~~~~python
memory = LongTermMemory(
    user_id=user_id,
    session_id=session_id,
    summary=summary_data.get("summary", ""),
    key_insights=summary_data,
    token_count=total_tokens,
)
~~~~

提交成功后，再把摘要、洞察和主题写入 Milvus，并把生成的 Milvus ID 回写到 milvus_ids。

所以一条记忆有两层持久化：

- PostgreSQL：列表、详情、所有权和删除依据。
- Milvus：相似度召回内容。

---

## 5. Milvus 记忆集合

集合名称固定为 long_term_memories，字段包括：

- id
- user_id
- session_id
- memory_type
- content
- metadata
- vector

向量维度是 1024，和当前 Embedding 配置一致。

一条 LongTermMemory 可能拆成多个向量：

- memory_id_summary
- memory_id_insight_0、memory_id_insight_1
- memory_id_topics

这样做可以分别召回摘要、知识点和主题，而不是把全部内容压成一个不可区分的向量。

---

## 6. 记忆检索为什么必须过滤 user_id

retrieve_memories 生成当前问题的向量后，使用：

~~~~text
user_id == 当前用户 ID
~~~~

作为 Milvus 过滤表达式。

如果没有这个过滤，不同用户的历史记忆可能互相召回。这是长期记忆系统最重要的隔离条件之一。

/memories/search、/memories/context/{query} 都从认证用户得到 user_id，不接受前端随意传入的 user_id。

---

## 7. build_memory_context 如何形成 Prompt 片段

它最多取 3 条相关记忆，按内容去重，然后拼成：

~~~~text
[相关历史记忆]
- 历史对话摘要: ...
- 相关知识点: ...
- 用户关注的主题: ...
~~~~

ChatService.get_chat_completion 只有在收到 user_id 参数时，才会调用 build_memory_context。

它随后把 memory_context 放入 Prompt，再放入参考文档、历史对话和当前问题。

---

## 8. 当前聊天调用链的真实限制

ChatService 的方法签名支持 user_id：

~~~~python
get_chat_completion(..., user_id=None)
~~~~

但当前 chat_router 的普通聊天调用主要传：

- session_id
- question
- retrieved_content

没有显式传入当前用户的 user_id。

因此静态源码能确认：

- 记忆服务、记忆 API 和 Prompt 注入代码已经存在。
- 通过 /memories/context/{query} 可以明确测试记忆召回。
- 不能仅凭普通聊天 Router 代码断言每次普通聊天一定自动注入当前用户记忆。

这类结论必须区分“能力存在”和“默认调用链已接通”。

---

## 9. 记忆页面做什么

frontend/src/pages/memory/index.tsx 当前支持：

- 获取当前用户的记忆列表。
- 按问题搜索语义相关记忆。
- 展示摘要、洞察、时间和相关度。
- 删除记忆。
- 刷新列表。

frontend/src/api/memory.ts 还定义了 createMemory 和 getMemoryContext，但当前页面主要展示列表、搜索和删除；是否有明显的创建入口，要以页面实际按钮和路由为准。

---

## 10. 删除记忆的双写清理

delete_memory 先按 memory_id 和 user_id 查询 PostgreSQL。

如果存在 milvus_ids：

1. 在 Milvus long_term_memories 中逐个删除向量。
2. 删除 PostgreSQL LongTermMemory。
3. 提交事务。

因此删除记忆比删除普通文档更明确地包含向量清理。排错时仍要验证 Milvus delete 是否成功，因为代码对向量删除异常是打印错误后继续删除数据库记录。

---

## 11. should_compress 的含义

MemoryService 通过简单字符估算 token：

~~~~text
估算 token = 文本长度 / 3
~~~~

超过 10000 时，should_compress 返回 true。

它表达了“对话过长时应该压缩”的策略，但当前源码中的显式创建接口仍由用户调用 /memories/create。不能看到阈值函数就推断系统已经自动定时压缩全部会话。

---

## 12. 故障排查示例

### 现象 A：记忆列表有记录，但搜索为空

检查：

1. Milvus long_term_memories 是否存在。
2. 向量是否真正插入。
3. Embedding 是否返回 1024 维向量。
4. 搜索 user_id 是否和写入值一致。
5. 查询问题是否生成了向量。

### 现象 B：记忆创建成功，但普通聊天没有利用

检查：

1. ChatService.get_chat_completion 是否收到 user_id。
2. Router 是否从认证用户取得并传递 user_id。
3. Prompt 日志中是否出现 [相关历史记忆]。
4. 直接调用 /memories/context/{query} 是否有结果。

---

## 13. 小练习

下面哪句话最准确？

A. 只要 LongTermMemory 写入 PostgreSQL，普通聊天就一定自动使用了这条记忆。

B. 长期记忆需要 PostgreSQL 元数据和 Milvus 向量共同支持；当前 ChatService 支持 user_id 注入，但普通聊天 Router 是否传入 user_id 还需要单独验证。

C. 长期记忆只保存在浏览器 localStorage。

D. 记忆搜索不需要 user_id 过滤。

---

## 留白：长期记忆链路

创建入口：

摘要字段：

PostgreSQL 字段：

Milvus 集合：

用户隔离条件：

Prompt 注入函数：

当前默认聊天调用的限制：

---

## 源码定位

- backend/app/router/memory_router.py：记忆 API 和会话归属检查
- backend/app/service/memory_service.py：总结、Embedding、Milvus 存储、召回和删除
- backend/app/models/chat.py：LongTermMemory
- backend/app/service/chat_service.py：可选的 memory_context 注入
- frontend/src/api/memory.ts：记忆接口契约
- frontend/src/pages/memory/index.tsx：记忆列表和搜索页面

