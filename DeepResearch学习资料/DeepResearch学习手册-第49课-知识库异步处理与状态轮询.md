# DeepResearch 学习手册·第 49 课

## 知识库异步处理与状态轮询

本课解决一个实际问题：用户上传文件后，为什么页面先显示“待处理”或“处理中”，过一会儿才变成“已完成”？前端如何知道后台处理到了哪一步？

---

## 1. 完整链路

~~~~text
选择文件
  ↓
前端 POST /knowledge-bases/{kb_id}/documents
  ↓
后端保存临时文件，并在 PostgreSQL 写入 Document(status=pending)
  ↓
接口立即返回“文档已上传，正在后台处理中”
  ↓
FastAPI BackgroundTasks 执行 process_document
  ↓
Document.status = processing
  ↓
DocMind 解析、切片、生成向量，并写入检索存储
  ↓
成功：status = completed，写入 chunk_count
失败：status = failed，写入 error_message
  ↓
前端定时 GET /knowledge-bases/{kb_id}/documents
  ↓
页面根据最新状态更新标签和按钮
~~~~

两个容易混淆的时间点：

1. 上传请求完成，只代表文件已经保存并创建了数据库记录。
2. 文档处理完成，才代表内容已经解析、切片并写入检索系统，可以用于 RAG。

所以“上传成功”不等于“已经可以检索”。

---

## 2. 后端为什么不在上传请求里一直等待

源码位置是 backend/app/router/knowledge_router.py 的 upload_document。

后端先做这些同步工作：

1. 校验 kb_id 和当前用户。
2. 检查扩展名是否在 ALLOWED_EXTENSIONS 中。
3. 把上传内容保存到 /tmp/knowledge_uploads。
4. 创建 Document 记录，初始 status="pending"。
5. 增加知识库的 document_count。
6. 提交事务并刷新文档 ID。

然后调用：

~~~~python
background_tasks.add_task(
    process_document,
    str(doc.id),
    file_path,
    kb.name,
    SessionLocal
)
~~~~

最后返回：

~~~~python
DocumentUploadResponse(
    id=str(doc.id),
    filename=doc.filename,
    process_status="pending",
    message="文档已上传，正在后台处理中"
)
~~~~

这样设计的效果是：上传接口不用等 DocMind、Embedding 和 Milvus 全部完成，用户可以较快得到响应。

### 一个工程上的边界

这里使用的是 FastAPI 的 BackgroundTasks。它适合当前项目这种简单后台任务，但它仍然依附于当前 Web 进程。它不是 Celery、RQ 或独立任务队列，因此不能自动提供完整的任务持久化、重试、跨机器调度和高可靠保证。

---

## 3. 四种文档状态

backend/app/models/knowledge.py 中的 Document.status 约定了四种状态：

| 状态 | 含义 | 用户能否查看切片 |
|---|---|---|
| pending | 数据库记录已创建，后台处理尚未开始或尚未更新状态 | 不能 |
| processing | 已进入文档解析和向量化流程 | 不能 |
| completed | 处理函数成功返回，chunk_count 已写入 | 可以 |
| failed | 处理函数返回失败或抛出异常 | 不能，先看错误信息 |

后台函数 process_document 会新建数据库会话，重新读取文档，然后把状态改为 processing 并提交：

~~~~python
doc = db.query(Document).filter(Document.id == document_id).first()
doc.status = "processing"
db.commit()
~~~~

它调用 process_document_with_docmind。如果结果成功：

~~~~python
doc.status = "completed"
doc.chunk_count = result["document_count"]
doc.error_message = None
~~~~

如果结果失败或抛出异常：

~~~~python
doc.status = "failed"
doc.error_message = str(e)
~~~~

无论成功还是失败，最后都会提交数据库事务，并在 finally 中关闭会话、删除临时文件。

---

## 4. 前端为什么要轮询

浏览器在上传请求返回后，不会自动知道后台任务何时完成。当前项目采用轮询：前端隔一段时间重新请求文档列表。

源码位置是 frontend/src/pages/knowledge/index.tsx。

组件有一个定时器引用：

~~~~tsx
const pollingRef = useRef<NodeJS.Timeout | null>(null)
~~~~

当当前知识库里存在 pending 或 processing 文档时，创建每 3 秒执行一次的定时器：

~~~~tsx
const hasProcessing = currentKnowledgeBase.documents.some(
  (doc) => doc.status === 'pending' || doc.status === 'processing'
)

if (hasProcessing) {
  pollingRef.current = setInterval(() => {
    knowledgeActions.refreshDocuments(currentKnowledgeBase.id)
  }, 3000)
}
~~~~

refreshDocuments 在 frontend/src/store/knowledge.ts 中调用：

~~~~ts
const res = await knowledgeApi.getDocuments(kbId)
if (knowledgeState.currentKnowledgeBase?.id === kbId) {
  knowledgeState.currentKnowledgeBase.documents = res.data
}
~~~~

于是 Valtio 状态变化，React 重新渲染，文档标签从“待处理”变成“处理中”或“已完成”。

---

## 5. 为什么处理完成后定时器会停止

轮询 useEffect 依赖 currentKnowledgeBase?.documents。每次文档列表更新后，Effect 会重新判断：

~~~~text
仍有 pending/processing？继续创建定时器
全部是 completed/failed？清除定时器
~~~~

清理函数是：

~~~~tsx
return () => {
  if (pollingRef.current) {
    clearInterval(pollingRef.current)
    pollingRef.current = null
  }
}
~~~~

组件卸载、切换知识库或依赖变化时都要清理定时器。否则用户离开页面后，旧页面仍可能继续请求接口，造成重复请求和内存泄漏。

组件最外层的 useEffect 还会在离开页面时调用 clearCurrentKnowledgeBase，并再次清理定时器。

---

## 6. 页面状态和真实检索状态的区别

页面显示 completed，说明后台函数报告成功，并把切片数写入了 PostgreSQL。真正检索时还要看向量检索服务是否能读到相应数据。

因此排错要分两层。

### 第一层：PostgreSQL 状态

检查：

~~~~text
Document.status
Document.chunk_count
Document.error_message
~~~~

如果状态是 failed，先看 error_message。

### 第二层：向量检索存储

检查：

~~~~text
DocMind 是否完成解析和切片
Embedding 是否成功
Milvus 对应 collection 是否存在
向量是否真的插入
检索时使用的 collection/index 名是否一致
~~~~

源码中知识库切片查询使用：

~~~~python
collection_name = "kb_" + kb.name.lower().replace(" ", "_")
~~~~

RAG 检索也必须使用同一套命名规则。数据库状态和向量库内容是两个系统，不能只查其中一个就断言“检索链路正常”。

---

## 7. 查看切片为什么必须要求 completed

前端的 handleViewChunks 先判断：

~~~~tsx
if (doc.status !== 'completed') {
  message.warning('文档尚未处理完成')
  return
}
~~~~

后端 GET /knowledge-bases/{kb_id}/documents/{doc_id}/chunks 也再次判断：

~~~~python
if doc.status != "completed":
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="文档尚未处理完成"
    )
~~~~

前端判断是用户体验保护，后端判断是接口边界保护。即使有人绕过前端直接调用接口，后端仍不会把未完成文档当作可用切片。

---

## 8. 故障排查示例

### 现象 A：一直停留在 pending

优先检查：

1. FastAPI 请求是否真的返回成功。
2. BackgroundTasks 是否被添加。
3. Web 进程是否在响应后立刻崩溃或重启。
4. 数据库中对应文档是否存在。

### 现象 B：变成 processing 后失败

优先检查：

1. 文件格式是否能被 DocMind 解析。
2. DocMind 服务地址和凭据是否正确。
3. Embedding 服务是否可访问。
4. Milvus 连接和 collection schema 是否匹配。
5. Document.error_message 和后端日志。

### 现象 C：显示 completed，但聊天检索不到

优先检查：

1. chunk_count 是否大于 0。
2. Milvus 是否有对应文件的切片。
3. 研究请求检索的索引是否是同一个索引。
4. 当前用户、知识库和检索参数是否匹配。
5. 重排模型是否把召回结果过滤或排序到了后面。

---

## 9. 本课必须掌握的四句话

1. 上传接口返回的是“文件已接收”，不是“知识库已可检索”。
2. pending → processing → completed/failed 是 PostgreSQL 中的文档状态机。
3. 前端每 3 秒读取文档列表，是为了把后台状态同步到页面。
4. completed 还需要结合向量库实际写入来验证 RAG 是否真的可用。

---

## 10. 小练习

只回答下面这一题即可：

一个文档页面显示“已完成”，但聊天检索不到它。你会优先检查哪一项？

A. 只检查 React 的颜色标签

B. 检查 Document.status 是否为 completed，以及 Milvus 中对应 collection 和切片是否真实存在

C. 重新刷新浏览器，但不看后端数据

D. 修改前端轮询间隔

建议先回答选项字母，再用一句话说明原因。

---

## 留白：你的笔记

> 在这里记录你对“上传完成”和“可检索”的区别、状态轮询的作用，以及你认为还需要验证的基础设施。




---

## 源码定位

- backend/app/router/knowledge_router.py：上传接口、后台处理函数、状态更新、切片接口
- backend/app/models/knowledge.py：KnowledgeBase 和 Document 数据模型
- backend/app/service/docmind_service.py：文档解析、切片、向量写入流程
- backend/app/service/milvus_service.py：向量集合和切片写入/查询
- frontend/src/pages/knowledge/index.tsx：知识库页面、状态标签、3 秒轮询、定时器清理
- frontend/src/store/knowledge.ts：上传后刷新、文档列表刷新和 Valtio 状态更新
- frontend/src/api/knowledge.ts：知识库和文档 HTTP 接口契约

