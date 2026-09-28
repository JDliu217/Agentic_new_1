# DeepResearch 学习手册·第 67 课

## 知识库文档：从上传到 Milvus 召回

知识库不是把文件路径直接交给 LLM，而是一条异步处理链：

```text
React 上传
  → POST /knowledge-bases/{kb_id}/documents
  → PostgreSQL Document(pending)
  → BackgroundTasks
  → processing
  → DocMind 解析
  → 文本切片
  → Embedding
  → Milvus 插入
  → completed
  → 前端轮询和检索
```

---

## 1. 上传接口先做什么

文件：`backend/app/router/knowledge_router.py`。

上传接口先：

1. 将路径参数转换为 UUID。
2. 查询知识库，并检查 `KnowledgeBase.user_id == current_user.id`。
3. 校验扩展名。
4. 把文件写入 `/tmp/knowledge_uploads`。
5. 创建 `Document` 记录。
6. 设置 `status="pending"`。
7. 增加知识库的 `document_count`。
8. 提交数据库事务。
9. 把 `process_document()` 放入 `BackgroundTasks`。

接口立即返回：

```json
{
  "id": "文档 ID",
  "filename": "文件名",
  "process_status": "pending",
  "message": "文档已上传，正在后台处理中"
}
```

所以“上传接口返回成功”只证明文件和数据库记录创建成功，不证明文档已经可以搜索。

---

## 2. 后台任务的状态变化

后台处理开始后，重新创建数据库 Session，按文档 ID查询记录，并把状态改为：

```text
pending → processing
```

处理成功：

```text
processing → completed
chunk_count = 切片数量
error_message = null
```

处理失败：

```text
processing → failed
error_message = 失败原因
```

无论成功失败，任务结束时都会关闭数据库 Session，并删除临时文件。

---

## 3. DocMind 解析和文本切片

文件：`backend/app/service/docmind_service.py`。

处理函数的顺序是：

```text
submit_job(file_path, file_name)
  → wait_for_completion(task_id)
  → collect_all_results(task_id)
  → chunk_text(text, chunk_size=500)
```

切片函数默认使用 500 字符左右的块，并尝试保留 50 字符的重叠关系。重叠的目的，是避免一个段落在切片边界被完全截断，便于召回时保留上下文。

这一步不是按用户问题切片，而是文档入库时预先切片。

---

## 4. Embedding 和 Milvus 插入

切片后调用 Embedding 服务生成向量。项目默认使用 `text-embedding-v4`，Milvus 服务按 1024 维向量配置。

每个切片会形成一条 Milvus 文档，主要字段包括：

```text
id
doc_id
kb_id
filename
content
chunk_index
vector
```

随后：

```text
get_milvus_service()
  → insert_documents(index_name, documents)
  → collection.insert()
  → collection.flush()
```

PostgreSQL 保存文档业务状态和权限元数据；Milvus 保存可用于语义搜索的切片向量和文本。两者缺一不可：只有 PostgreSQL 没有向量，无法做高效语义召回；只有 Milvus 没有业务记录，无法稳定管理权限、状态和文件生命周期。

---

## 5. 前端为什么轮询

文件：`frontend/src/pages/knowledge/index.tsx`。

页面发现当前知识库中有文档处于 `pending` 或 `processing` 时，会每 3 秒调用：

```text
refreshDocuments(currentKnowledgeBase.id)
```

当没有处理中状态时停止轮询；组件卸载时也会 `clearInterval`。

因此前端显示的“处理中”来自 PostgreSQL 文档状态，而不是 Milvus 的实时状态。

---

## 6. 当前集合命名风险

后台任务使用：

```python
index_name = f"kb_{kb_name}".lower().replace(" ", "_")
```

Milvus 文档中的 `kb_id` 也写入这个集合名，而不是知识库 UUID。

这会带来几个风险：

- 知识库重命名后，旧集合名和新名称可能不一致。
- 不同用户使用相同知识库名称时可能发生集合冲突。
- DeepScout 如果使用固定集合名，上传链和研究检索可能找不到同一批向量。
- 名称清洗规则不完整时，特殊字符可能造成集合名问题。

更稳定的方案是使用不可变的 `kb_id` 生成集合名，例如：

```text
kb_{knowledge_base_uuid_without_hyphens}
```

并让上传、删除、切片查看、检索和 DeepResearch 全部使用同一配置或显式集合名。

---

## 7. “完成”不等于“可检索”

排错时要分别确认：

1. PostgreSQL `Document.status == completed`。
2. `chunk_count` 大于 0。
3. Milvus 目标集合存在。
4. Milvus 集合实体数量大于 0。
5. 向量维度与集合 Schema 一致。
6. 召回时使用了正确的集合名。
7. `kb_id` 过滤值与插入值一致。

如果页面显示 completed 但搜索为空，优先查 Milvus 集合、过滤条件和 Embedding，而不是先修改前端搜索列表。

---

## 8. 与普通聊天附件的区别

知识库文档：

```text
Document
  → DocMind
  → 切片
  → Embedding
  → Milvus
  → 长期检索
```

普通聊天附件：

```text
ChatAttachment
  → content_text
  → 当前 /chat/completion/v3 Prompt
  → 当前回答
```

当前普通 PDF、Word、图片附件主要写入占位文本，不等同于知识库 DocMind 解析。

---

## 练习

假设页面显示文档 `completed`，但本地知识库搜索结果为空。请按顺序列出至少四条需要检查的证据。

参考答案方向：检查 PostgreSQL 的 `chunk_count`；确认目标 Milvus 集合名称和实体数量；确认 Embedding 是否成功且维度正确；确认检索使用的集合名、`kb_id` 过滤和 DeepScout 的集合配置一致。

