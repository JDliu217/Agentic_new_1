# DeepResearch 学习手册·第 26 课

## RAG：从知识库上传到 DeepScout 召回

本课解释“文档为什么能被 Agent 搜到”。不要只记住“用了向量数据库”，要能追踪一份文件从浏览器上传开始，经过解析、切片、Embedding、Milvus 写入，最后变成 Scout 可分析的搜索结果。

源码依据：

```text
D:\课\s4-6\industry_information_assistant\backend\app\router\knowledge_router.py
D:\课\s4-6\industry_information_assistant\backend\app\service\docmind_service.py
D:\课\s4-6\industry_information_assistant\backend\app\service\embedding_service.py
D:\课\s4-6\industry_information_assistant\backend\app\service\milvus_service.py
D:\课\s4-6\industry_information_assistant\backend\app\service\deep_research_v2\agents\scout.py
D:\课\s4-6\industry_information_assistant\frontend\src\pages\knowledge\index.tsx
```

---

## 1. 先理解 RAG 在本项目中解决什么问题

LLM 本身不知道你刚上传的企业报告。RAG（检索增强生成）的基本过程是：

```text
用户文档
  → 切成多个文本块
  → 每个文本块转换成向量
  → 向量和原文一起存储

用户问题
  → 转换成查询向量
  → 在向量库找相近文本块
  → 把召回内容交给 Agent/LLM 分析
```

向量用于“相似度搜索”，原文用于“阅读、引用和生成答案”。因此 PostgreSQL、Embedding 和 Milvus 各自保存不同东西，不能互相替代。

---

## 2. 新知识库页面的上传链路

前端入口是 `pages/knowledge/index.tsx`：

```text
用户选择文件
  → handleUpload(file)
  → knowledgeActions.uploadDocument(kbId, file)
  → knowledgeApi.uploadDocument(kbId, file)
  → POST /knowledge-bases/{kb_id}/documents
```

请求是 `multipart/form-data`。后端允许的扩展名包括 PDF、Word、文本、表格、演示文稿、图片、代码和 JSON 等，但“允许上传”只表示接口接受该扩展名，不代表每一种类型都已经被 DocMind 成功解析。

### 2.1 后端上传接口先做什么

`knowledge_router.upload_document()` 按顺序执行：

1. 把路径参数解析为 UUID。
2. 按当前用户检查知识库是否存在。
3. 检查文件扩展名。
4. 把文件写到 `/tmp/knowledge_uploads`。
5. 在 PostgreSQL 创建 `Document` 记录，初始状态为 `pending`。
6. 增加知识库的 `document_count`。
7. 提交 `BackgroundTasks`：调用 `process_document(...)`。
8. 立即返回 `process_status: "pending"`。

所以前端看到“上传成功”时，通常只代表文件已保存、数据库记录已建立、后台任务已排队；不代表向量已经写入 Milvus。

---

## 3. 后台文档处理：`pending` 到 `completed`

`process_document()` 使用新的数据库会话读取文档，并把状态改成：

```text
pending → processing → completed
                    ↘ failed
```

它按知识库名称生成集合名：

```python
index_name = f"kb_{kb_name}".lower().replace(" ", "_")
```

然后调用 `process_document_with_docmind()`。

### 3.1 DocMind 解析

`DocMindService` 的真实顺序是：

```text
submit_job(file_path, file_name)
  → query_status(task_id)
  → 每 5 秒轮询一次
  → 最多等待 300 秒
  → get_result(task_id, layout_num, layout_step_size)
  → collect_all_results(task_id)
```

`collect_all_results()` 会分页读取布局块，优先提取 `markdownContent`，其次尝试 `text`，直到没有更多布局或单页数量少于步长。

如果提交失败、解析失败、超时或最终文本为空，文档会变成 `failed`，错误写入 `error_message`。

### 3.2 文本切片

默认 `chunk_text(text, chunk_size=500, overlap=50)`：

```text
每块目标长度：500 个字符
相邻块重叠：50 个字符
优先在句号、问号或换行处切分
```

重叠的作用是减少关键信息刚好被切断后，两个块都缺少上下文的概率。块太小会让上下文不足，块太大会降低检索精度并增加上下文成本。

### 3.3 生成 Embedding

`generate_embedding(chunks)` 调用阿里 DashScope 的 `text-embedding-v4`：

```text
向量维度：1024
批量大小：最多 10 个文本
```

列表输入会按 10 条一批发送；某批失败时，该批会补充 `None`，后续数量检查可能使整个文档处理失败。缺少 `DASHSCOPE_API_KEY` 时不会得到有效向量。

### 3.4 写入 Milvus

每个文本块会生成一个记录，核心字段是：

```text
id          当前切片 ID
doc_id      原始文件 ID
kb_id       知识库标识
filename    文件名
content     切片原文
chunk_index 块序号
vector      1024 维向量
```

`MilvusService.create_collection()` 使用：

```text
集合名：kb_<知识库名称>
距离：COSINE
索引：IVF_FLAT
nlist：128
```

成功插入后，后台任务把 PostgreSQL 文档状态改为 `completed`，并把切片数量写入 `chunk_count`。临时文件随后被删除；原始文档内容主要留在 Milvus 的 `content` 字段和向量记录中。

---

## 4. 前端为什么要轮询

知识库页面发现当前文档中有 `pending` 或 `processing` 状态时，会建立一个 3 秒间隔的定时器：

```text
setInterval(
  () => refreshDocuments(currentKnowledgeBase.id),
  3000
)
```

组件卸载、切换知识库或不再需要轮询时，会调用 `clearInterval`。轮询请求的是 `GET /knowledge-bases/{kb_id}/documents`，不是查询 Milvus；页面依据 PostgreSQL 中的 `Document.status` 更新显示。

查看切片时，前端只允许 `completed` 文档继续，请求：

```text
GET /knowledge-bases/{kb_id}/documents/{doc_id}/chunks
```

后端会验证用户、知识库、文档和完成状态，然后按 `kb_<name>` 集合、文件名查询 Milvus 并按 `chunk_index` 排序。

注意：切片接口捕获 Milvus 异常后返回空数组。页面显示“没有切片”不一定意味着文档真的没有切片，也可能是 Milvus 查询失败。

---

## 5. DeepScout 如何执行本地向量搜索

研究请求中的 `search_modes` 会在 `research_router` 转成 `search_local`。Scout 读取这个开关后，在每个研究查询中调用：

```text
_execute_local_search(query)
  → generate_embedding(query)
  → MilvusService.search(...)
  → top_k=10
  → 格式化为统一搜索结果
```

当前 `_execute_local_search()` 固定使用：

```python
collection_name="knowledge_base"
```

返回结果会被转换成与网页搜索近似的结构：

```text
url、title、summary、snippet、score、kb_id、doc_id、chunk_index
```

Scout 随后把网页结果和本地结果合并，交给 `_analyze_search_results()`，由 LLM 提取事实、数据点、来源和洞察。

---

## 6. 一个关键集成风险：集合名称没有贯通

上传链使用：

```text
kb_<实际知识库名称>
```

通用 `retrieval_service.retrieve_from_knowledge_base(kb_name, ...)` 也会使用：

```text
kb_<传入名称>
```

但 V2 的 DeepScout 本地搜索固定查：

```text
knowledge_base
```

同时，`DeepResearchV2Service.research()` 虽然接收 `kb_name`，调用 `graph.run()` 时没有继续把它放入 `ResearchState`；`ResearchState` 也没有 `kb_name` 字段。

因此准确结论是：

> 知识库上传和独立检索接口支持按知识库名称建集合，但 V2 Scout 当前没有完整接收和使用指定知识库名称。

可能出现的现象是：文档上传和处理都成功，页面也显示 `completed`，但 DeepResearch 的本地检索仍然搜不到该文档。

这不是“向量搜索算法不行”，而是集合选择契约没有贯通。

---

## 7. 三条容易混淆的文档链

### 7.1 新知识库管理链

```text
/knowledge-bases
→ PostgreSQL KnowledgeBase/Document
→ DocMind
→ kb_<name> Milvus 集合
→ 知识库页面和 V2 本地搜索（当前存在集合名风险）
```

### 7.2 旧外部文档服务链

项目还有 `/documents/*` 路由和 `DocumentService`。它可以通过旧的外部文档服务配置进行上传、列表、删除和检索，不能因为路由名称相近就认为它等于新知识库链。

其中 `/documents/upload` 也调用本地 `process_document_with_docmind()`，但使用传入的 `index_name`，默认值是 `policy_documents`，属于兼容/独立入口。

### 7.3 政策文档链

`PolicySearchService` 使用固定 `policy_documents` 集合：

```text
hybrid_search → vector_search
keyword_search → vector_search
vector_search → Embedding → Milvus COSINE
```

所以方法名叫 `hybrid` 或 `keyword`，不代表当前实现真的执行了关键词与向量混合检索；源码中两者都会降级到纯向量搜索。

---

## 8. 如何判断一次 RAG 链路到底成功了

不要只检查上传接口的 HTTP 200。至少分四层：

```text
1. 上传层：POST 返回 pending，文件和 Document 记录存在
2. 处理层：Document.status=completed，chunk_count>0
3. 存储层：Milvus 对应集合存在，实体数量增加
4. 召回层：用实际问题生成向量，搜索结果包含目标文档内容
```

如果第 1 层成功而第 2 层失败，查 DocMind、文件格式、Embedding 密钥和后台日志；如果第 2 层成功而第 4 层失败，优先查集合名称、查询开关、Embedding 维度和过滤条件。

当前环境尚未完成 PostgreSQL、Milvus、DocMind 和 DashScope 的真实端到端验证，所以本课描述的是源码证据和可推导的数据流，不代表外部依赖已经在本机运行成功。

---

## 9. 练习

请用自己的话回答：

1. 为什么上传接口返回成功时，文档仍可能不能被搜索？
2. `chunk_size=500`、`overlap=50` 分别影响什么？
3. PostgreSQL 的 `Document` 记录和 Milvus 的向量记录为什么要同时存在？
4. V2 Scout 固定搜索 `knowledge_base` 会造成什么问题？如何设计一个完整修复方案？
5. `keyword_search()` 当前为什么不能被称为真正的关键词检索？

