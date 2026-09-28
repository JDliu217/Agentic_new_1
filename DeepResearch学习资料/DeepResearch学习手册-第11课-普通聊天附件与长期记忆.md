# DeepResearch 学习手册：第 11 课

## 普通聊天、附件与长期记忆

DeepResearch 不是项目唯一的聊天能力。普通聊天、附件问答和长期记忆构成另一条重要支线。理解它们能帮助你区分：普通聊天是“检索后回答”，DeepResearch 是“规划、证据、分析、写作和审核”。

---

## 1. 普通聊天的请求链路

当前普通聊天的主要链路是：

```text
React Chat 页面
  → frontend/src/api/session.ts::chat
  → POST /chat/completion
  → backend/app/router/chat_router.py::chat_completion_v2
  → 本地政策检索 + Web 搜索
  → rerank_documents()
  → ChatService.get_chat_completion()
  → LLM 流式输出
  → SSE 事件返回前端
```

旧版 `/chat/completion/v1` 还保留了另一条知识库检索路径，使用 `DocumentService` 和默认 dataset；当前 `/chat/completion` 则使用 `retrieve_content()` 查询 `policy_documents`，再合并网络结果。

这说明项目存在兼容层：接口名称相近，但内部检索实现并不完全相同。

---

## 2. 普通聊天的四步处理

### 第一步：检索

根据请求开关决定是否搜索本地知识库和互联网：

```text
search_knowledge=True
  → retrieve_content(policy_documents)

search_web=True
  → WebSearchService.retrieve_from_web()
```

### 第二步：合并

把政策/知识库文档和网络文档放入同一个列表。

### 第三步：重排

`ChatService.rerank_documents()` 使用 DashScope 重排模型重新计算相关度，然后：

- 按权重从高到低排序。
- 最多保留 10 个文档。
- 使用 tokenizer 控制总上下文 token 不超过 12000。
- 为每份文档重新编号。

### 第四步：生成

`get_chat_completion()` 会把以下内容拼入提示词：

```text
长期记忆（如果 user_id 可用）
参考文档
历史会话消息
当前问题
```

LLM 以流式方式返回回答，结束时再发送文档引用和 `[DONE]`。

---

## 3. 引用为什么要经过重排

搜索返回的第一条结果不一定最适合当前问题。重排模型会重新比较“问题”和“候选文档”的相关性。

可以把它理解为：

```text
搜索：先尽量找一批候选
重排：再从候选中挑最适合放进提示词的内容
```

如果重排服务失败，源码会回退到原始 `weight` 排序。这是可用性优先的 fallback，但质量可能下降。

---

## 4. 会话历史的双轨结构

项目当前同时存在两套会话实现。

### 4.1 新会话系统：PostgreSQL

文件：

```text
backend/app/router/session_router.py
backend/app/service/session_service.py 之外的 SQLAlchemy 会话模型
backend/app/models/chat.py::ChatSession / ChatMessage
frontend/src/api/session.ts
frontend/src/store/session.ts
```

接口：

```text
GET    /sessions
POST   /sessions
GET    /sessions/{id}
PUT    /sessions/{id}
DELETE /sessions/{id}
POST   /sessions/{id}/messages
```

这套系统带用户归属、会话类型、消息引用和附件关系。

### 4.2 旧聊天系统：Redis

文件：

```text
backend/app/service/session_service.py
backend/app/router/chat_router.py
```

它把会话存成 Redis Hash，把消息 ID 存入 Sorted Set，并限制历史消息数量和 prompt token 数。

### 4.3 阅读时必须警惕的集成边界

前端新建会话使用 `/sessions`，但旧聊天路由内部仍通过 Redis `SessionService` 检查会话。两套系统的 ID 形式相似，但数据不在同一个存储里。阅读或调试时，必须确认当前页面最终调用的是哪套接口，不能因为都叫 session 就假设它们共享数据。

这不是理论问题，而是当前源码的真实结构。后续工程推进应考虑统一会话存储，或明确旧接口的兼容转换规则。

---

## 5. 附件上传和附件问答

### 5.1 上传链路

```text
前端选择文件
  → POST /attachments
  → 保存到 /tmp/chat_attachments
  → 创建 ChatAttachment 记录，status=pending
  → BackgroundTasks 调用 process_attachment()
  → status=processing
  → 提取文本
  → status=completed 或 failed
```

前端会轮询 `GET /attachments/{attachment_id}`，直到看到处理结果。

### 5.2 当前附件解析能力

这些文本/代码类型会直接读取文件：

```text
txt、md、py、js、ts、json、yaml、yml、xml、csv、html
```

PDF、Word 和图片当前主要写入占位文本，例如“PDF 文件：xxx”，还没有接入完整的 PDF、Word 或 OCR 解析。因此聊天附件和知识库文档不能混为同一条解析链路。

### 5.3 带附件聊天

```text
POST /chat/completion/v3
  → 读取已完成附件的 content_text
  → 每个附件最多取 10000 字符
  → 拼入 enhanced_question
  → 再做知识库/Web 检索
  → 调用 ChatService 生成回答
```

注意：附件文本被拼入问题上下文，知识库和网络检索仍然是独立步骤。

---

## 6. 长期记忆的数据流

### 6.1 创建记忆

```text
会话消息
  → LLM 总结 summary/key_insights/topics
  → PostgreSQL LongTermMemory
  → summary、insight、topics 分别生成 Embedding
  → Milvus long_term_memories collection
```

PostgreSQL 记录完整记忆对象和 Milvus ID；Milvus 保存用于语义召回的向量。

### 6.2 搜索记忆

```text
用户问题
  → Embedding
  → Milvus 按 user_id 过滤
  → COSINE 相似度搜索
  → 返回 summary/insight/topics
```

`build_memory_context()` 会去重后把结果格式化成提示词上下文。

### 6.3 当前接入边界

`ChatService.get_chat_completion()` 支持传入 `user_id`，但当前 `chat_router.py` 的普通聊天调用没有传 `user_id`。因此“长期记忆服务已实现”不等于“当前每次普通聊天都会自动使用长期记忆”。阅读源码时要区分“函数具备能力”和“调用链实际接通”。

---

## 7. 前端页面对应关系

| 功能 | 前端入口 | 后端接口 |
|---|---|---|
| 普通聊天 | `pages/chat/index.tsx` | `/chat/completion` |
| DeepResearch | `pages/chat/index.tsx` | `/research/stream` |
| 上传聊天附件 | `pages/chat/index.tsx` / `newchat.tsx` | `/attachments` |
| 知识库文档 | `pages/knowledge/index.tsx` | `/knowledge-bases/...` |
| 记忆列表/搜索 | `pages/memory/index.tsx` | `/memories` |
| 创建会话记忆 | 记忆页面操作 | `/memories/create` |

---

## 8. 本课排错题

### 情况 A：附件状态一直 processing

检查：后台任务是否执行、文件路径是否存在、扩展名是否进入解析分支、数据库状态是否提交。

### 情况 B：附件上传成功，但回答只说“这是某 PDF 文件”

这可能不是 SSE 问题，而是当前源码对 PDF 只保存占位文本，尚未集成完整解析器。

### 情况 C：普通聊天没有历史消息

检查当前调用的是 PostgreSQL 会话 API 还是 Redis `SessionService`，再检查聊天路由是否找到了对应 Redis session。

### 情况 D：记忆页面能搜索，但聊天回答没有使用记忆

检查 `user_id` 是否从认证上下文一路传给 `get_chat_completion()`。不要只检查 `MemoryService` 本身。

---

## 9. 本课掌握标准

你应该能画出三条独立数据流：

```text
普通聊天：检索 → 重排 → 历史/记忆上下文 → LLM → SSE
附件聊天：上传 → 后台解析 → content_text → enhanced_question → 聊天链路
长期记忆：会话 → LLM 摘要 → PostgreSQL + Milvus → 语义召回
```

并能指出：旧 Redis 会话、新 PostgreSQL 会话、知识库文档解析和聊天附件解析不是同一个实现。

