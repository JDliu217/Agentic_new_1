# DeepResearch 学习手册·第 57 课

## 普通聊天附件和知识库文档的区别

这两个功能都能“上传文件”，但用途、存储和后续检索方式不同。混淆它们会导致错误排查。

---

## 1. 两条链路先对比

### 普通聊天附件

~~~~text
文件
  ↓
POST /attachments
  ↓
ChatAttachment(status=pending)
  ↓
BackgroundTasks.process_attachment
  ↓
content_text
  ↓
/chat/completion/v3
  ↓
把附件文本直接拼进当前问题
  ↓
本次回答结束
~~~~

### 知识库文档

~~~~text
文件
  ↓
POST /knowledge-bases/{kb_id}/documents
  ↓
Document(status=pending)
  ↓
DocMind 解析
  ↓
切片
  ↓
Embedding
  ↓
Milvus
  ↓
后续聊天或研究反复召回
~~~~

普通附件是当前会话的临时上下文；知识库文档是可长期检索的资料。

---

## 2. 普通附件的数据库模型

ChatAttachment 位于 backend/app/models/chat.py，主要字段：

- session_id
- user_id
- filename
- file_type
- file_size
- file_path
- content_text
- status
- error_message

它与 ChatSession 关联，但没有直接把内容写入 Milvus。

因此看到 ChatAttachment.completed，含义是 content_text 已准备好，不是已经完成向量入库。

---

## 3. 普通附件上传流程

backend/app/router/attachment_router.py 的 upload_attachment 会：

1. 解析 session_id。
2. 查询 ChatSession 是否存在。
3. 检查扩展名。
4. 使用 UUID 加原文件名生成临时文件名。
5. 保存到 /tmp/chat_attachments。
6. 创建 ChatAttachment，初始 status=pending。
7. 添加 process_attachment 后台任务。
8. 立即返回附件响应。

前端先生成一个临时 ID，界面显示 uploading；收到真实响应后，用后端附件 ID 替换临时 ID。

---

## 4. 附件处理能力有明显边界

process_attachment 对纯文本和代码类文件会直接读取内容：

- txt
- md
- py
- js
- ts
- json
- yaml
- xml
- csv
- html

但 PDF、Word 和图片当前主要写入占位文本：

~~~~text
[PDF 文件: 文件名]
[Word 文档: 文件名]
[图片: 文件名]
~~~~

这意味着附件状态 completed 并不等于 PDF 或图片已经被真正理解。它只表示这段占位文本已经写入 content_text。

知识库文档链路才使用更完整的 DocMind 解析、切片和向量化。

---

## 5. 前端为什么每 2 秒轮询附件

frontend/src/pages/chat/index.tsx 会筛选 pending 或 processing 附件。

只要存在未完成附件，就每 2 秒调用：

~~~~text
GET /attachments/{attachment_id}
~~~~

当所有附件都不再是 pending 或 processing 时，清理定时器。

组件卸载时也会清除定时器，避免离开聊天页面后仍然请求。

---

## 6. v3 聊天怎样使用附件

前端发送：

~~~~json
{
  "session_id": "会话 ID",
  "question": "用户问题",
  "attachment_ids": ["附件 ID"]
}
~~~~

后端 /chat/completion/v3 查询每个附件。只有以下条件同时满足，才会加入上下文：

- ID 格式有效。
- 附件记录存在。
- content_text 有值。
- status=completed。

然后构造：

~~~~text
用户问题：原始问题

请结合以下上传的附件内容来回答问题：

=== 用户上传的附件内容 ===
--- 文件名 ---
附件文本
=== 附件内容结束 ===
~~~~

最终这个增强后的问题和普通召回内容一起交给 ChatService.get_chat_completion。

---

## 7. 为什么附件内容有长度限制

后端每个附件读取后最多保留 50000 个字符；v3 读取附件内容加入上下文时还会截断到 10000 个字符。

这是为了避免：

- Prompt 过长。
- LLM token 超限。
- 单个大文件挤掉知识库和历史对话。
- 请求耗时和费用不可控。

这也意味着“大文件上传成功”不等于模型看到了完整文件。

---

## 8. 发送消息和保存历史

frontend/src/pages/chat/index.tsx 的 send 会：

1. 先把用户消息放进前端列表。
2. 调用 /sessions/{id}/messages 保存用户消息。
3. 调用普通聊天、附件聊天或 DeepResearch SSE。
4. 收集助手回答。
5. 再保存助手消息、思考内容和 references_data。
6. 发送后清空前端附件列表。

所以“聊天流”和“消息历史持久化”是两条并行关注点：

- SSE 负责实时体验。
- ChatMessage 负责刷新后恢复历史。

---

## 9. 普通附件不适合什么场景

不适合：

- 多个会话长期共享同一资料。
- 需要按语义搜索大文档。
- 需要按切片显示来源。
- 需要跨请求持续召回。
- 需要大量 PDF、Word 和图片的真实解析。

这些需求应该进入知识库文档链路，并验证 DocMind、Embedding 和 Milvus。

---

## 10. 当前实现需要留意的授权边界

附件 Router 使用 get_current_user，而不是必须认证依赖。部分附件接口只检查附件 ID 或 session 是否存在，没有像 /sessions 那样始终验证 session 属于当前用户。

这是源码层面的安全审计点：学习时应区分“功能链路能工作”和“资源授权已经严密”。

---

## 11. 一次故障排查例子

现象：附件显示已完成，但模型回答“没有附件内容”。

按顺序检查：

1. ChatAttachment.content_text 是否有真实内容。
2. 对于 PDF/Word/图片，内容是否只是占位文本。
3. 前端发送的 attachment_ids 是否是真实后端 ID。
4. 后端 v3 是否筛选到了 status=completed 的附件。
5. 增强后的 question 是否包含附件上下文。
6. Prompt 是否因长度截断。
7. 是否真的调用了 /chat/completion/v3，而不是普通 /chat/completion。

---

## 12. 小练习

用户上传 PDF 附件，页面显示 completed，但模型只能看到“[PDF 文件: xxx.pdf]”。最准确的解释是什么？

A. Milvus 向量搜索失败

B. 当前普通附件处理器对 PDF 只写入占位文本，没有真正解析 PDF

C. 前端 2 秒轮询太慢

D. JWT 一定过期

---

## 留白：两种文件链路笔记

普通附件的最终文本位置：

知识库文档的向量位置：

普通附件是否进入 Milvus：

PDF 当前处理结果：

可跨会话长期检索的方案：

---

## 源码定位

- backend/app/router/attachment_router.py：附件上传、后台处理和删除
- backend/app/models/chat.py：ChatAttachment、ChatSession、ChatMessage
- backend/app/router/chat_router.py：v3 附件上下文拼接
- frontend/src/api/session.ts：附件和 v3 API
- frontend/src/pages/chat/index.tsx：附件轮询、上传和消息保存
- backend/app/router/knowledge_router.py：知识库文档完整入库链

