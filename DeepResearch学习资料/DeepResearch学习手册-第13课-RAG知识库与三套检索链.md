# DeepResearch 学习手册·第 13 课

## RAG 知识库与三套检索链

> 本课依据本地源码整理。源码位置：`D:\课\s4-6\industry_information_assistant`。
> 本课描述的是当前实现，不把注释中的设计目标当成已经接通的功能。

## 1. 先建立全局认识

RAG（Retrieval-Augmented Generation，检索增强生成）可以拆成两个动作：

1. 先从外部资料中找出与问题相关的片段。
2. 再把片段放进模型上下文，让模型基于证据回答。

项目里“知识库”不是一个单独的类，而是三条历史阶段不同的链路：

| 链路 | 入口 | 主要存储 | 当前用途 |
| --- | --- | --- | --- |
| 新知识库管理链 | `/knowledge-bases` | PostgreSQL + Milvus | 创建知识库、上传文件、解析、切片、向量检索 |
| 旧外部文档服务链 | `/documents/*` | 外部 RAGFlow 兼容服务 | 通过 `dataset_id` 管理和检索文档 |
| 政策文档链 | `PolicySearchService` | Milvus 的 `policy_documents` 集合 | 行业政策搜索；关键词和 hybrid 当前降级为向量搜索 |

DeepResearch V2 的 `DeepScout` 还带有一条本地检索实现。它直接搜索名为 `knowledge_base` 的 Milvus 集合，这与新知识库上传时生成的 `kb_<知识库名>` 集合名不一致，存在“上传成功但研究 Agent 找不到”的集成风险。

## 2. 新知识库管理链：从上传到检索

### 2.1 创建知识库

前端调用 `knowledge_router.py` 的知识库接口。后端把知识库名称和说明写进 PostgreSQL 的 `KnowledgeBase` 表，并用 UUID 标识知识库。

知识库记录和向量集合是两层对象：

- PostgreSQL 记录回答“这个知识库是谁、属于谁、有哪些文档”。
- Milvus 集合回答“这些文档切片的向量和原文是什么”。

两者通过知识库名称、文档 ID、`kb_id` 等字段关联，不能把 Milvus 当成业务主数据库。

### 2.2 上传文档

上传接口会完成以下工作：

1. 校验当前用户和目标知识库。
2. 在 PostgreSQL 创建 `Document` 记录。
3. 把文件暂存到上传目录。
4. 启动后台处理任务。
5. 处理成功后更新状态、切片数量和错误信息。

文档状态大致经历：`pending` → `processing` → `completed` 或 `failed`。

因此，HTTP 上传成功只代表任务已经受理，不等于文档已经可以检索。前端还应该查看文档状态。

### 2.3 DocMind 解析

`docmind_service.py` 的处理顺序是：

```text
本地文件
→ DocMind 提交解析任务
→ 轮询任务完成
→ 收集解析结果
→ 得到纯文本
```

DocMind 负责处理复杂文档的结构化解析。当前代码随后把各页或各布局结果拼成一段文本，再进入通用切片函数。图片、表格的结构保留程度取决于 DocMind 返回内容和收集逻辑，不能仅凭文件扩展名保证完整还原。

### 2.4 文本切片

`chunk_text()` 默认每块约 500 个字符，重叠 50 个字符。切片时优先在 `。！？？.!?\n` 等边界处截断，避免把一句话从中间切开。

切片的目的不是越小越好：

- 太大：一次检索带入太多无关内容，模型上下文浪费。
- 太小：上下文断裂，单块缺少主题和条件。
- 有重叠：相邻块共享部分上下文，降低边界信息丢失。

当前实现是按字符长度的启发式切片，不是按标题、段落、表格或语义边界做的层次化切片。

### 2.5 Embedding

每个文本块调用 `embedding_service.py` 生成向量。查询时对用户问题执行同样的向量化，只有查询向量和文档向量处在同一个模型空间，Milvus 的相似度才有意义。

这一层的输入输出是：

```text
文本块列表[str]
→ Embedding API
→ 向量列表[list[float]]
```

代码会检查“向量数量是否等于切片数量”。如果数量不一致，整份文档处理失败，避免切片和向量错位。

### 2.6 写入 Milvus

每个切片会生成类似下面的记录：

```text
id           = 当前文件名、切片序号和内容前缀的 MD5
doc_id       = 文件名的 MD5
kb_id        = kb_<知识库名>
filename     = 原文件名
content      = 切片原文
chunk_index  = 切片序号
vector       = Embedding 向量
```

集合名由知识库名称生成：

```python
collection_name = f"kb_{kb_name}".lower().replace(" ", "_")
```

例如知识库名 `新能源 政策` 会映射到 `kb_新能源_政策`。名称修改后，新的集合名也会变化；这意味着重命名策略需要额外考虑数据迁移，当前代码没有展示完整的迁移流程。

### 2.7 查询路径

`retrieval_service.py` 的查询过程是：

```text
问题
→ generate_embedding([问题])
→ Milvus.search(collection_name, query_vector, top_k)
→ 格式化为 document_id、document_name、content、score
```

`retrieve_from_knowledge_base(kb_name, question)` 会把知识库名称转换成 `kb_<知识库名>`，因此它能够和新知识库上传路径匹配。

## 3. 旧外部文档服务链

`document_service.py` 代表另一套接口。它不负责直接操作本地 Milvus，而是向配置的外部文档服务发送请求，例如：

```text
/documents/*
→ DocumentService
→ 外部 RAGFlow 兼容 API
→ dataset_id
→ 外部服务负责解析、切片、向量化和召回
```

这套链路的关键是 `dataset_id`，而新知识库链路的关键是 PostgreSQL 的知识库记录和本地 Milvus 集合。二者的字段、生命周期和异常排查方式都不同。

如果接口返回“文档上传成功”，需要确认成功发生在哪一层：

- 只是本地文件保存成功；
- 外部服务已创建文档；
- 外部服务已完成解析；
- 外部索引已可检索。

## 4. 政策文档 Milvus 链

`PolicySearchService` 默认使用 `policy_documents` 集合，并为政策记录保存标题、网站、入口 URL、详情 URL、日期、正文和向量。

查询方法包括：

- `vector_search()`：真正执行 Milvus 向量搜索。
- `keyword_search()`：注释明确说明 Milvus 不直接支持关键词搜索，当前调用 `vector_search()`。
- `hybrid_search()`：当前同样调用 `vector_search()`，还不是向量 + 关键词的混合召回。

所以 API 名字中的“keyword”和“hybrid”不能直接当作当前实现能力。面试或项目介绍时应准确说“接口预留了两种模式，但当前实现降级为纯向量搜索”。

## 5. DeepResearch V2 的本地搜索

`DeepScout._execute_local_search()` 的当前行为是：

```text
研究问题
→ generate_embedding(query)
→ Milvus.search(collection_name="knowledge_base")
→ 格式化为本地来源
```

它没有使用 `kb_name` 拼接 `kb_<知识库名>`，而是固定搜索 `knowledge_base`。这与 `knowledge_router.py` 和 `retrieval_service.py` 的命名规则不同。

### 5.1 这会造成什么问题

假设用户创建了名为 `金融政策` 的知识库：

1. 上传链路把数据写入 `kb_金融政策`。
2. 普通知识库检索按 `kb_金融政策` 查询，可以命中。
3. V2 DeepScout 固定查询 `knowledge_base`，可能查不到同一批切片。

这不是 RAG 原理问题，而是系统集成契约不一致。修复时需要统一集合命名策略，或让 DeepScout 接收知识库名并调用统一的 `retrieval_service`。

## 6. 一次完整的证据链

以“知识库中有哪些政策要求？”为例，理想链路如下：

```text
用户上传政策 PDF
→ PostgreSQL 创建 Document
→ DocMind 解析文本
→ chunk_text 切片
→ Embedding API 生成向量
→ Milvus 写入 kb_政策
→ 用户提问
→ 问题 Embedding
→ Milvus 相似度召回 top_k
→ Agent 把切片整理成证据
→ Writer 生成带来源的回答
→ 前端渲染回答和来源
```

排错时沿这条链逐段确认，不要只看最后的模型回答：

1. PostgreSQL 是否有文档记录？状态是否为 `completed`？
2. DocMind 是否返回非空文本？
3. 切片数量是否大于 0？
4. Embedding 数量是否和切片数量一致？
5. 目标 Milvus 集合是否存在？是否有实体？
6. 查询向量是否成功生成？
7. 检索的集合名是否和上传时完全一致？
8. Agent 是否真正把召回内容放进提示词？
9. 最终回答中的来源是否来自这些召回片段？

## 7. 当前实现的边界

- 新知识库链路依赖 PostgreSQL、Milvus、Embedding 服务和 DocMind；缺少其中任一服务，真实端到端流程都无法完整验证。
- `PolicySearchService` 的 keyword/hybrid 目前不是独立召回算法。
- DeepScout 的固定集合名与新知识库命名规则不一致。
- 当前切片主要按字符和标点，复杂表格、标题层级和跨页语义可能损失。
- 向量相似度只是相关性信号，不等于事实正确性；需要来源展示、重排、引用校验或人工复核。
- 文档状态成功只说明处理函数成功返回，仍需要检查 Milvus 集合中的实际数据。

## 8. 你需要掌握的核心词汇

| 词 | 在本项目中的含义 |
| --- | --- |
| Chunk | 文档被切成的一个可检索文本片段 |
| Embedding | 把文本映射为向量的模型或服务 |
| Milvus | 保存向量并执行相似度搜索的向量数据库 |
| Collection | Milvus 中类似表的集合 |
| Top-K | 返回最相关的 K 个切片 |
| Recall | 从知识库找候选证据 |
| Rerank | 对候选证据重新排序，当前项目没有统一的独立重排链 |
| Grounding | 让回答建立在可追溯证据上 |
| Dataset ID | 旧外部文档服务链中的数据集标识 |

## 9. 课后练习

1. 解释为什么文档上传接口返回 200 不代表“马上能搜到”。
2. 给出 `kb_政策` 这个集合名是在哪里生成的。
3. 说明 `PolicySearchService.keyword_search()` 为什么不能称为真正的关键词搜索。
4. 画出新知识库链路和旧外部文档服务链路的差异。
5. 假设召回为空，按第 6 节的 9 个检查点写一份排错顺序。
6. 解释为什么 DeepScout 固定搜索 `knowledge_base` 可能导致集成问题。

## 10. 留白与笔记

### 我的理解

<!-- 在这里写你对 RAG 的一句话理解 -->


### 我还不懂的词

<!-- 在这里补充术语和问题 -->


### 源码证据

<!-- 在这里记录你亲自打开并读过的文件和行号 -->


### 我会如何修复集合命名不一致

<!-- 在这里画方案或写伪代码 -->


### 面试表达

<!-- 用 3-5 句话向面试官讲清本课内容 -->

