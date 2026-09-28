# DeepResearch 学习手册·第 20 课

## 知识库上传、异步解析与向量检索前端链路

> 本课依据本地项目 `D:\课\s4-6\industry_information_assistant\frontend` 与 `backend` 的知识库源码整理。重点是区分“文件已经上传”“文档已经解析”“切片已经写入向量库”和“研究请求能够检索到它”这几个不同状态。

---

## 1. 四个阶段

用户点击上传后，系统经历：

```text
文件到达后端并写入临时目录
  → PostgreSQL 创建 Document，状态 pending
  → 后台任务解析、切片、Embedding、写入 Milvus
  → Document 状态 completed，之后才可以查看切片和检索
```

| 现象 | 能证明什么 | 不能证明什么 |
|---|---|---|
| 上传接口成功 | 文件和文档记录创建成功 | 向量已经写入 |
| 显示处理中 | 后台任务尚未完成 | 解析一定成功 |
| 显示已完成 | 后端任务报告成功 | 研究 Agent 一定查询了该集合 |
| 能查看切片 | Milvus 按文件名查到切片 | 查询一定召回正确内容 |

---

## 2. 前端知识库页面

主要文件：

```text
frontend/src/pages/knowledge/index.tsx
frontend/src/store/knowledge.ts
frontend/src/api/knowledge.ts
frontend/src/components/upload-modal/index.tsx
frontend/src/components/chunks-drawer/index.tsx
```

`knowledgeState` 保存：

```ts
{
  knowledgeBases: KnowledgeBase[],
  currentKnowledgeBase: KnowledgeBaseWithDocuments | null,
  loading: boolean,
  uploading: boolean
}
```

组件本地状态保存弹窗、上传文件名、上传结果和当前查看的文档。跨页面业务数据放在 Valtio，弹窗等一次性 UI 状态放在 `useState`。

进入页面后，登录状态成立时调用 `GET /knowledge-bases`；点击知识库后调用 `GET /knowledge-bases/{kb_id}`，详情响应包含文档列表。

---

## 3. 知识库 CRUD

创建链路：

```text
KnowledgePage.handleCreateKb
  → knowledgeActions.createKnowledgeBase
  → knowledgeApi.createKnowledgeBase
  → POST /knowledge-bases
```

编辑调用 `PUT /knowledge-bases/{kb_id}`，删除调用 `DELETE /knowledge-bases/{kb_id}`。后端数据库模型对文档关系配置了级联删除；向量库中的集合或向量是否同步清理，需要检查具体删除实现，不能只看到 PostgreSQL 删除就断言 Milvus 已清空。

---

## 4. 浏览器上传链路

页面使用 Ant Design `Upload` 的 `beforeUpload={handleUpload}`。`handleUpload(file)` 会：

1. 打开上传 Modal。
2. 记录文件名并清空上一次结果。
3. 调用 `knowledgeActions.uploadDocument()`。
4. 写入成功或失败结果。
5. 返回 `false`，阻止 Upload 组件再次自动上传。

API 文件构造 `FormData`：

```ts
const formData = new FormData()
formData.append('file', file)
```

请求是 `POST /knowledge-bases/{kb_id}/documents`，使用 `multipart/form-data`。上传请求配置为：

```ts
loading: false
cancelRepeat: false
timeout: 300000
```

上传 Modal 显示“上传完成”时，真实含义是文件已上传、后台开始处理，并不是解析已经完成。真正状态来自 `pending / processing / completed / failed`。

---

## 5. 前端状态轮询

当当前知识库中存在 `pending` 或 `processing` 文档时，页面每 3 秒调用：

```http
GET /knowledge-bases/{kb_id}/documents
```

返回的新列表写入 `currentKnowledgeBase.documents`。文档变为 `completed` 或 `failed` 后轮询停止；组件卸载时清理 `setInterval`。

当前处理中进度条固定显示 `30`，不是后端真实百分比，所以只能表示“任务仍在运行”。多个标签页可能重复轮询；后台异常也可能造成长期 processing。

---

## 6. FastAPI 上传接口

文件：`backend/app/router/knowledge_router.py`，接口：

```python
@router.post("/{kb_id}/documents")
async def upload_document(...)
```

### 6.1 校验和临时文件

后端依次把 `kb_id` 转成 UUID、按 `kb_id` 和 `current_user.id` 查询知识库、检查扩展名是否在 `ALLOWED_EXTENSIONS`。前端 `accept` 只影响文件选择器，后端检查才是实际约束。

文件保存到 `/tmp/knowledge_uploads`。当前源码以知识库 UUID 和原始文件名组成路径，工程上应进一步检查路径穿越、特殊字符和同名覆盖风险。

### 6.2 创建 Document

后端创建记录：

```text
knowledge_base_id
user_id
filename
file_type
file_size
file_path
status = pending
chunk_count = 0
```

同时将 `KnowledgeBase.document_count` 加一并提交事务。此时数据库记录已经存在，即使后续处理失败，也会保留为 `failed` 并记录错误信息。

### 6.3 加入后台任务

```python
background_tasks.add_task(
    process_document,
    str(doc.id),
    file_path,
    kb.name,
    SessionLocal,
)
```

接口立即返回 `process_status = pending` 和“文档已上传，正在后台处理中”。

---

## 7. 后台解析、切片和向量化

### 7.1 状态变为 processing

后台函数重新创建数据库 Session，根据文档 ID 查询记录，将状态从 `pending` 改为 `processing`。使用新的 Session 是因为原 HTTP 请求的 Session 生命周期已接近结束。

### 7.2 DocMind

`process_document_with_docmind()` 调用：

```text
DocMindService.submit_job()
  → wait_for_completion()
  → collect_all_results()
```

提交失败、超时或结果为空都会返回失败信息。

### 7.3 文本切片

`chunk_text()` 默认 `chunk_size = 500`、`overlap = 50`。代码尽量在句号、问号、感叹号或换行处结束一块，下一块从上一块结束位置减去 50 开始。重叠可减少语义跨块断裂，但会增加向量数量和检索成本。

### 7.4 Embedding 和 Milvus

切片送入 `generate_embedding(chunks)`，代码要求向量不为空且数量与切片数量相等。每个切片包含：

```text
id, doc_id, kb_id, filename, content, chunk_index, vector
```

集合名称是：

```python
index_name = f"kb_{kb_name}".lower().replace(" ", "_")
```

然后调用 `milvus.insert_documents(index_name, documents)`。

成功时设置 `Document.status = completed`、写入 `chunk_count` 并清空错误信息；失败时设置 `failed` 和 `error_message`。任务最后提交事务并删除临时文件。

---

## 8. 查看切片

文档不是 `completed` 时，前端按钮被禁用，`handleViewChunks()` 也会阻止打开抽屉。完成后 `ChunksDrawer` 调用：

```http
GET /knowledge-bases/{kb_id}/documents/{doc_id}/chunks
```

后端再次检查用户、知识库、文档归属和 completed 状态，然后用同一规则生成集合名并按文件名从 Milvus 读取切片。

如果 Milvus 查询异常，当前后端捕获异常并返回空切片数组。页面可能显示“暂无切片”，实际原因却是向量库故障，排错时必须结合后端日志。

---

## 9. 从切片到 RAG 检索

文件：`backend/app/service/retrieval_service.py`。

```text
问题
  → generate_embedding([question])
  → Milvus.search(collection_name, query_vector, top_k)
  → 格式化 document_id、document_name、content、score
  → 交给聊天服务或研究 Agent 作为上下文
```

最小 RAG 闭环是：

```text
文档 → 切片 → Embedding → Milvus
问题 → Embedding → Top-K 相似度检索 → LLM 上下文
```

PostgreSQL 保存用户、知识库、文档状态等关系数据；Milvus 保存向量和切片内容，两者职责不同。

---

## 10. 关键集成风险：集合命名必须贯通

上传和查看切片使用 `kb_<知识库名称>`，但 V2 `DeepScout._execute_local_search()` 当前固定搜索过 `knowledge_base`。因此可能出现：

```text
上传成功
数据库状态 completed
Milvus 中有向量
DeepResearch 仍然找不到
```

阅读时要追踪：

```text
页面选择的知识库
  → 请求是否带 kb_name 或 kb_id
  → ResearchState 是否保存它
  → Scout 使用哪个 collection_name
```

当前审计已确认，`kb_name` 从研究服务入口没有完整传入 `graph.run()`，`ResearchState` 也没有对应字段。这是跨模块集成边界，不是 UI 问题。

---

## 11. 练习

1. 上传接口返回 `pending` 时，为什么不能立即查看切片？
2. 从 `handleUpload()` 写到 `process_document_with_docmind()`，列出至少 8 个中间步骤。
3. 页面长期显示“处理中”时，你会依次查看浏览器 Network、文档 API、PostgreSQL 状态、后台日志、DocMind、Embedding 和 Milvus 的哪些证据？
4. 一个文档切成 20 个块而 Embedding 只返回 19 个时，代码当前会如何处理？
5. 给出知识库名称后，写出上传链、切片查看链和检索链的集合名，并判断是否一致。

---

## 12. 面试官追问

1. 为什么上传接口不等待解析完成？
2. `BackgroundTasks` 和 Celery/RQ 任务队列有什么差异？
3. 文档状态存在 PostgreSQL，切片为什么还要放 Milvus？
4. overlap 对召回有什么帮助，代价是什么？
5. 如何避免同一文件重复上传造成重复向量？
6. 如何证明上传文档真的被 DeepResearch 检索到了？
7. 如果 Milvus 故障被返回为空数组，用户如何区分“没有结果”和“系统故障”？
8. 知识库重命名后旧集合如何处理？
9. 为什么用稳定 `kb_id` 通常比用名称作为集合标识更可靠？

---

## 13. 本课结论

```text
React Upload
  → multipart/form-data
  → FastAPI 权限与扩展名校验
  → PostgreSQL Document(pending)
  → BackgroundTasks
  → DocMind 解析
  → 文本切片
  → Embedding
  → Milvus collection
  → 前端轮询 completed
  → 切片查看或 RAG Top-K 检索
```

只看到“上传成功”不能证明 RAG 已经可用，必须同时核对数据库状态、向量库状态和研究 Agent 的集合选择。

---

## 14. 留白与我的笔记

### 14.1 我画的知识库数据流

<!-- 补充前端、FastAPI、PostgreSQL、DocMind、Embedding、Milvus 的箭头关系。 -->



### 14.2 我需要验证的外部依赖

<!-- 记录 DocMind、Embedding、Milvus、PostgreSQL 是否可连通，以及验证命令或接口。 -->



### 14.3 我发现的状态或命名风险

<!-- 记录 pending/processing/completed/failed 或集合名称方面的风险。 -->



### 14.4 面试回答草稿

<!-- 用自己的话回答本课第 12 节问题。 -->



