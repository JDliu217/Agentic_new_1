# DeepResearch 学习手册·第 111 课：RAG 从上传到召回的完整链路

## 1. RAG 是什么

RAG（Retrieval-Augmented Generation）可以拆成两步：

```text
先从自己的资料库检索相关内容
→ 再把检索结果交给 LLM 生成回答或报告
```

它解决的问题是：模型本身不知道你的私有文档，或者模型知识不足以支持当前问题。RAG 不是重新训练模型，而是在请求时把相关证据补进上下文。

本项目的知识库链路可以分成两条时间线：

```text
离线/上传时间线：文件 → 文本 → 切片 → 向量 → Milvus
在线/提问时间线：问题 → 查询向量 → Milvus 相似搜索 → Agent 证据
```

## 2. 上传入口和用户边界

文件：`backend/app/router/knowledge_router.py:289-375`

用户上传时，请求大致是：

```text
POST /knowledge-bases/{kb_id}/documents
Content-Type: multipart/form-data
```

后端执行顺序：

1. 把 `kb_id` 转成 UUID；
2. 使用 `KnowledgeBase.id == kb_uuid` 和 `KnowledgeBase.user_id == current_user.id` 查询；
3. 检查扩展名是否在允许列表；
4. 文件写入 `/tmp/knowledge_uploads`；
5. 创建 `Document`，初始 `status="pending"`；
6. 增加知识库的文档计数；
7. 注册 `BackgroundTasks` 处理任务；
8. 立即向前端返回 pending。

这里的返回成功只表示“文件记录已创建、后台任务已安排”，不表示文档已经完成解析或已经写入 Milvus。

## 3. 文档状态机

`process_document()` 位于 `knowledge_router.py:75-120`：

```text
pending
  → processing
  → completed
  → failed
```

后台任务先重新创建数据库会话，再查找文档并更新为 `processing`。任务成功后写入 `chunk_count` 并改为 `completed`；任意异常都会写入 `error_message` 并改为 `failed`。最后关闭数据库会话并删除临时文件。

这说明 PostgreSQL 中的 Document 状态是任务状态记录，不是 Milvus 内容的直接证明。排查时必须同时查看状态、日志和向量集合。

## 4. DocMind 处理链

文件：`backend/app/service/docmind_service.py:250-360`

`process_document_with_docmind()` 的真实步骤：

```text
1. DocMindService.submit_job(file_path, file_name)
2. wait_for_completion(task_id)
3. collect_all_results(task_id)
4. chunk_text(text, chunk_size=500)
5. generate_embedding(chunks)
6. 组装 Milvus 文档记录
7. milvus.insert_documents(index_name, documents)
```

如果文本为空、切片失败、Embedding 返回空或向量数量与切片数量不一致，函数会返回 `success=False`，上层将文档标记为 `failed`。

每个向量记录包含：

```text
id
doc_id
kb_id
filename
content
chunk_index
vector
```

## 5. Embedding 的作用

文件：`backend/app/service/embedding_service.py:24-97`

项目使用 DashScope 的 `text-embedding-v4`，默认输出 1024 维向量。Embedding 的输入是文本，输出是数字列表；Milvus 保存的是数字列表和原文本元数据。

必须满足：

```text
写入向量维度 == Milvus 集合 vector 字段维度
```

缺少 `DASHSCOPE_API_KEY` 时，函数返回 `None`，上传任务会失败或无法形成可搜索向量。

## 6. Milvus 写入

文件：`backend/app/service/milvus_service.py:39-123`

`insert_documents()` 先调用 `create_collection(collection_name)`，集合字段包括 `content`、`kb_id`、`chunk_index` 和 1024 维 `vector`。索引使用 COSINE 相似度和 IVF_FLAT。

上传路由把知识库名称转换成集合名：

```python
index_name = f"kb_{kb_name}".lower().replace(" ", "_")
```

例如知识库名称为 `新能源 政策`，集合名会是：

```text
kb_新能源_政策
```

## 7. 在线检索的通用路径

文件：`backend/app/service/retrieval_service.py:17-92`

通用检索函数的步骤：

```text
问题
→ generate_embedding([question])
→ 取 query_vector
→ MilvusService.search(collection_name, query_vector, top_k, kb_id)
→ 把命中记录格式化为 document_id/document_name/content/score
```

旧的 `retrieve_from_knowledge_base(kb_name, question)` 会把知识库名转换为 `kb_<name>`，因此它与上传链路的命名规则一致。

## 8. DeepScout 的本地搜索路径

文件：`backend/app/service/deep_research_v2/agents/scout.py:1005-1058`

当 `ResearchState.search_local=True` 时，DeepScout：

1. 为查询生成向量；
2. 调用 `MilvusService.search()`；
3. 固定传入 `collection_name="knowledge_base"`；
4. 将命中结果转换为 `local://kb/...` 来源格式；
5. 返回给后续事实提取和报告写作。

## 9. 当前源码已证明的集合命名风险

上传链路写入：

```text
kb_<知识库名称>
```

DeepScout 查询：

```text
knowledge_base
```

因此下面的现象完全可能发生：

```text
PostgreSQL Document.status = completed
Milvus 中确实有向量
DeepScout 本地搜索结果 = 0
```

这不一定是 Embedding 失败，可能只是读写集合不同。调查时要打印并比较：

```text
上传时的 index_name
实际存在的 Milvus 集合列表
DeepScout 查询的 collection_name
kb_id 过滤值
```

## 10. 一次完整 RAG 数据流

```text
用户创建知识库
  → PostgreSQL KnowledgeBase(user_id, name)

用户上传文件
  → Document(pending)
  → BackgroundTasks
  → Document(processing)
  → DocMind 文本解析
  → 文本切片
  → DashScope Embedding
  → Milvus 写入
  → Document(completed)

用户发起研究并打开 local 模式
  → ResearchState.search_local=True
  → DeepScout 生成查询向量
  → Milvus search
  → facts/raw_sources/references
  → DataAnalyst/LeadWriter 使用证据
```

## 11. 常见故障的证据顺序

### 情况 A：上传接口直接报错

检查 token、知识库归属、文件扩展名、临时目录和 PostgreSQL。

### 情况 B：上传成功但一直 pending

检查 BackgroundTasks 是否执行、数据库连接是否能在后台重新建立、后端日志是否出现 `processing`。

### 情况 C：状态变成 failed

查看 `Document.error_message`，再检查 DocMind 凭证、解析任务、文本结果、Embedding API 和向量维度。

### 情况 D：状态 completed 但本地搜索为空

按集合名、Milvus 健康状态、query embedding、`kb_id` 过滤和 `search_local` 请求开关依次检查。

### 情况 E：搜索有结果但报告没引用

检查 DeepScout 是否把结果写入 `facts`/`references`，LeadWriter 是否读取这些字段，以及 SSE 和前端引用事件是否正常。

## 12. 练习

1. 为什么上传接口返回 `pending` 时，不能告诉用户“文档已经可以搜索”？
2. 说出 `Document.status` 和 Milvus 中向量记录的区别。
3. 如果 Embedding 维度是 1536，而 Milvus 集合定义为 1024，会在哪个阶段出问题？
4. 用一句话解释上传链路写入 `kb_x`、DeepScout 查询 `knowledge_base` 会造成什么结果。
5. 请把“文件上传到 DeepScout 召回”按 8 个步骤复述出来。

