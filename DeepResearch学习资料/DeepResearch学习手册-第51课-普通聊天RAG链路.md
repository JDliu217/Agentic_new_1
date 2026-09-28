# DeepResearch 学习手册·第 51 课

## 普通聊天的 RAG 链路：召回、重排、Prompt 和 SSE

本课回答一个核心问题：

> 一个普通聊天问题，怎样从浏览器进入后端，拿到知识库内容，交给大模型，并把答案和来源流式返回？

---

## 1. 三个聊天入口不是同一条实现

前端 API 位于 frontend/src/api/session.ts：

| 接口 | 用途 | 主要知识来源 |
|---|---|---|
| POST /chat/completion/v1 | 旧版普通聊天 | DocumentService 的默认数据集，加 Web 搜索 |
| POST /chat/completion | 当前新版普通聊天 | policy_documents 检索，加 Web 搜索 |
| POST /chat/completion/v3 | 带附件聊天 | policy_documents 检索，加 Web 搜索和已处理附件 |

它们都返回 SSE，但知识库检索实现不同。

学习时不能只看“都是聊天接口”，必须继续追踪每个 Router 里面实际调用了哪个 Service。

---

## 2. 入口一：旧版 v1

backend/app/router/chat_router.py 中的 /completion/v1 大致执行：

~~~~text
接收 ChatRequest
  ↓
检查 session_id，不存在时创建旧会话
  ↓
如果 search_knowledge=true
  → ChatService.retrieve_from_knowledge_base
  → DocumentService.retrieve_documents
  ↓
如果 search_web=true
  → ChatService.retrieve_from_web
  ↓
合并 knowledge_docs 和 web_docs
  ↓
ChatService.rerank_documents
  ↓
ChatService.get_chat_completion
  ↓
StreamingResponse(text/event-stream)
~~~~

旧版知识库检索使用配置里的 default_dataset_id。它不是直接传知识库名称去查当前用户的 KnowledgeBase，而是调用外部文档服务的 dataset。

---

## 3. 入口二：新版普通聊天

POST /chat/completion 的关键路径是：

~~~~python
retrieved_data = retrieve_content(
    indexNames="policy_documents",
    question=request.question
)
~~~~

retrieve_content 在 backend/app/service/retrieval_service.py 中执行：

1. 对用户问题调用 generate_embedding。
2. 取得查询向量。
3. 获取 Milvus 服务。
4. 调用 milvus.search。
5. 把结果整理成 document_id、document_name、content_with_weight、score。

当前新版接口随后把每条结果转换为 ChatService 能识别的字典：

~~~~python
{
    "id": item["id"],
    "content": item["content_with_weight"],
    "source": "文档名称和 ID",
    "document_id": item["document_id"],
    "document_name": item["document_name"]
}
~~~~

然后把这些政策文档与 Web 搜索结果合并。

---

## 4. 召回阶段到底做了什么

召回就是先从大量知识片段中找出一小批候选片段。

当前向量召回流程：

~~~~text
问题文本
  ↓
text-embedding-v4
  ↓
问题向量
  ↓
Milvus collection.search
  ↓
按 COSINE 相似度返回 top_k
  ↓
候选切片列表
~~~~

Milvus 搜索使用向量字段 vector，默认返回 top_k=5；集合不存在时直接返回空列表。

这解释了一个常见现象：

- 没有异常日志；
- API 仍然返回 200；
- 但候选文档为空。

因为检索服务在多个失败位置都把结果降级为空列表，上层可能继续生成一个没有参考资料的回答。

---

## 5. 重排阶段为什么还要存在

初次向量召回只负责找到候选，不一定能把最相关的内容排在第一位。ChatService.rerank_documents 会：

1. 取出每个候选的 content。
2. 使用 DashScopeRerank 对问题和文本重新评分。
3. 把分数写入 weight。
4. 按 weight 从高到低排序。
5. 按 token 上限过滤。
6. 最多保留 10 个文档。

代码中的 token 上限是 12000。它不是简单地“只取前 10 条”，而是先检查累计 token，超过上限的文档会跳过。

如果重排服务出错，代码会退回到每个文档原来的 weight，再按原权重排序。这种 fallback 保证了回答流程可能继续，但也会降低排序质量。

---

## 6. 没有检索结果时会发生什么

ChatService.get_chat_completion 发现 retrieved_content 为空时，会构造：

~~~~text
知识库没有找到相关内容, 请结合你自己的知识回答
~~~~

然后仍然调用大模型。

所以“模型回答出来了”不能证明 RAG 成功。必须同时观察：

- 检索结果数组是否为空。
- 返回的文档名称和分数。
- Prompt 中是否真的出现参考内容。
- 最终 SSE 是否发送了 documents 事件。

这是 RAG 系统中“生成成功”和“检索成功”的区别。

---

## 7. Prompt 是怎样组装的

get_chat_completion 会组装四类信息：

1. 长期记忆上下文。
2. 编号化的参考内容。
3. 会话历史。
4. 当前用户问题。

参考内容类似：

~~~~text
[1] [knowledge] 第一条文档内容 (相关度: 0.92)
[2] [web] 第二条网页摘要 (相关度: 0.81)
~~~~

Prompt 要求模型：

- 根据参考内容回答。
- 每块内容标注来源编号。
- 没有参考内容时明确说明。
- 保持历史对话连贯。
- 如果提供长期记忆，结合记忆回答。

这里的来源编号只是 Prompt 中的约定，前端显示来源还要依赖后续 SSE 的 documents 事件。

---

## 8. SSE 返回顺序

后端调用 OpenAI 兼容接口并设置 stream=true。每收到一段模型输出，就发送：

~~~~text
event: message
data: {"role":"assistant","content":"一小段回答","thinking":false}

~~~~

模型结束后，后端再发送检索来源：

~~~~text
event: message
data: {"documents":[...]}

~~~~

最后发送：

~~~~text
event: end
data: [DONE]

~~~~

因此前端必须同时处理：

- 增量回答文本。
- 可能的 reasoning_content。
- documents 来源列表。
- end 结束事件。
- error 错误事件。

来源可能在回答文本之后到达，不能只在第一个 message 事件时读取。

---

## 9. 前端如何消费普通聊天流

frontend/src/pages/chat/index.tsx 的 sendChat：

1. 根据聊天类型调用 deepsearch、chat 或 chatWithAttachments。
2. 从响应中取得 ReadableStream reader。
3. 循环 reader.read。
4. 使用 TextDecoder 把字节转成文字。
5. 把数据追加到临时缓冲区。
6. 以换行符为边界拆出 data 行。
7. 去掉 data: 前缀并 JSON.parse。
8. 更新当前聊天项。
9. 流结束后把 loading 设为 false。

为什么需要缓冲区：

一次 reader.read 不保证刚好对应一条完整 SSE 消息。一个 JSON 可能被拆成两次读取，也可能一次读取包含多条消息。只有等到换行符，才能把完整数据行交给 JSON.parse。

---

## 10. 带附件 v3 的特殊处理

/ chat/completion/v3 会先根据 attachment_ids 查询 ChatAttachment。

只有满足以下条件的附件才会加入 Prompt：

- ID 格式有效。
- 数据库中存在记录。
- content_text 有内容。
- status=completed。

附件内容会被拼接成：

~~~~text
=== 用户上传的附件内容 ===
--- 文件名 ---
附件文本
=== 附件内容结束 ===
~~~~

然后增强用户问题，再交给 get_chat_completion。

因此附件的上传完成和附件内容可用也是两个状态。上传接口返回不等于解析完成；前端还会轮询附件状态。

---

## 11. 当前实现中的两个重要边界

### 11.1 普通聊天路由没有显式传入 user_id

ChatService.get_chat_completion 支持 user_id 参数，并且只有 user_id 存在时才构造长期记忆上下文。但当前 chat_router 调用它时主要传 session_id、question 和 retrieved_content，没有显式传入用户 ID。

因此源码能证明“记忆能力被实现”，不能仅凭静态代码证明“普通聊天一定注入了当前用户记忆”。需要真实请求或进一步修改调用链验证。

### 11.2 旧会话和新会话不是同一个存储

/ sessions 路由使用 PostgreSQL 的 ChatSession 和 ChatMessage；旧 / chat/session 使用 Redis SessionService。聊天接口名称相近，但会话存储可能不同，不能默认共享历史消息。

---

## 12. 一次完整的普通聊天数据流

~~~~text
React sender
  ↓
frontend/src/api/session.ts
  ↓
POST /chat/completion
  ↓
chat_router.chat_completion_v2
  ↓
retrieve_content
  ↓
Embedding + Milvus search
  ↓
WebSearchService（如果开启）
  ↓
rerank_documents
  ↓
Prompt 组装
  ↓
OpenAI 兼容 LLM stream
  ↓
SSE message/documents/end
  ↓
ReadableStream 缓冲和 parseData
  ↓
聊天文本和来源组件
~~~~

---

## 13. 小练习

一个普通聊天问题已经成功生成了回答，但返回的 documents 数组为空。下面哪一项判断最正确？

A. 一定说明模型服务不可用。

B. 只能说明生成阶段成功，不能证明知识库召回成功；应继续检查 embedding、Milvus search 和过滤条件。

C. 只要回答有内容，就说明 RAG 一定成功。

D. 只需要把前端轮询时间改短。

---

## 留白：我的数据流笔记

接口：

知识库召回函数：

重排函数：

Prompt 中的参考内容：

SSE 结束事件：

我认为最容易混淆的两个存储：

---

## 源码定位

- backend/app/router/chat_router.py：三个普通聊天入口
- backend/app/service/retrieval_service.py：Embedding 到 Milvus 检索
- backend/app/service/chat_service.py：召回结果格式化、重排、Prompt 和 SSE
- backend/app/service/embedding_service.py：向量和重排模型调用
- frontend/src/api/session.ts：聊天 API 契约
- frontend/src/pages/chat/index.tsx：ReadableStream 缓冲和事件解析

