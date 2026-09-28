# DeepResearch 学习手册：第 74 课

## RAG：从上传文档到 Agent 召回

RAG 可以先理解为：

```text
先从自己的资料库找到相关内容
再把相关内容交给 LLM 生成回答
```

它不是重新训练模型，而是在每次问题到来时动态提供证据。

## 1. 知识库中有两种数据

项目同时使用 PostgreSQL 和 Milvus，但它们保存的不是同一种东西。

### PostgreSQL 保存业务元数据

`KnowledgeBase` 和 `Document` 主要保存：

```text
知识库 ID
知识库名称
用户 ID
文件名
文件类型
文件大小
文件路径
处理状态
切片数量
错误信息
```

### Milvus 保存检索数据

Milvus 保存：

```text
文档切片正文
切片对应的向量
文件名
文档 ID
知识库 ID
切片序号
```

一句话记忆：

```text
PostgreSQL 知道“有哪些文件、处理到哪一步”
Milvus 负责“根据问题找到哪些内容”
```

## 2. 上传接口做什么

入口：

```text
POST /knowledge-bases/{kb_id}/documents
```

在 `knowledge_router.py` 中，上传接口大致执行：

```text
验证当前用户拥有这个知识库
→ 检查文件扩展名
→ 保存临时文件
→ 创建 Document(status="pending")
→ 增加知识库 document_count
→ 添加 BackgroundTasks
→ 立即返回上传结果
```

因此前端收到上传成功时，只能说明“文件已登记并等待处理”，不能说明文档已经可以检索。

## 3. 文档状态为什么要轮询

后台处理状态通常是：

```text
pending
  → processing
  → completed
       或
     failed
```

前端需要定时请求文档列表或文档详情，直到状态变为 `completed` 或 `failed`。

原因是处理链包含外部服务和多个耗时步骤：

```text
DocMind 解析
→ 轮询解析任务
→ 收集布局块
→ 合并文本
→ 文本切片
→ 生成向量
→ 写入 Milvus
```

## 4. DocMind 解析和文本切片

`docmind_service.py::process_document_with_docmind()` 主要步骤是：

1. 提交文档解析任务。
2. 轮询任务状态。
3. 分页获取 `layouts`。
4. 合并 Markdown 或文本内容。
5. 调用 `chunk_text()` 切片。

默认切片参数大致是：

```text
chunk_size = 500
overlap    = 50
```

重叠部分的作用是减少一句话刚好被切断后，前后片段都缺少上下文的问题。

例如：

```text
第一片：A B C D E
第二片：E F G H I
```

`E` 的重复就是 overlap 的简化示意。

## 5. Embedding 做什么

Embedding 服务把文本变成数字向量：

```text
“电池价格下降的原因”
→ [0.12, -0.04, ..., 0.81]
```

项目默认使用：

```text
text-embedding-v4
1024 维向量
```

重要的是：向量不是答案，而是文本语义位置的数字表示。以后用户搜索问题时，也要用同一个向量模型把问题转换成向量，才能进行相似度比较。

## 6. 写入 Milvus

处理流程会为每个切片构造记录，包含：

```text
content
filename
doc_id
kb_id
chunk_index
vector
```

然后：

```text
创建或打开 collection
→ 插入数据
→ flush
→ 建立/使用向量索引
→ load collection
```

Milvus 的搜索使用向量相似度，项目的核心搜索方式是 COSINE 相似度。

## 7. 查询时发生什么

一个问题进入检索服务后，大致是：

```text
用户问题
→ 生成问题向量
→ 指定 Milvus collection
→ top_k 相似度搜索
→ 取回 content、filename、doc_id、score
→ 转成 Agent 或聊天服务可使用的结果
```

研究 Agent 的本地搜索入口在：

```text
backend/app/service/deep_research_v2/agents/scout.py
```

它根据 `ResearchState["search_local"]` 决定是否执行本地搜索。

## 8. 当前项目的重要集合名风险

通用检索服务 `retrieve_from_knowledge_base()` 通常根据知识库名称生成：

```text
kb_<知识库名称>
```

例如：

```text
知识库名称：新能源汽车报告
collection：kb_新能源汽车报告
```

但 DeepScout 的 `_execute_local_search()` 当前固定使用：

```text
collection_name = "knowledge_base"
```

这会产生一种很容易误判的现象：

```text
Document 状态 = completed
Milvus 中确实写入了 kb_新能源汽车报告
DeepResearch 本地搜索 = 空结果
```

此时不能只看 PostgreSQL 的 `completed` 状态，还要比较：

```text
写入集合名
查询集合名
是否相同
```

## 9. 文档完成不等于可召回

一个文档要真正被 DeepResearch 使用，至少要经过：

```text
Document completed
→ DocMind 有文本结果
→ chunks 数量大于 0
→ embedding 数量和 chunks 数量一致
→ Milvus 插入成功
→ collection 名称一致
→ collection 已 load
→ 查询向量维度一致
→ top_k 搜索返回结果
→ DeepScout 把结果写入事实或来源
```

其中任何一步失败，都可能表现为“本地知识库没有结果”。

## 10. RAG 和模型训练的区别

本项目的知识库不是把文档重新训练进模型参数，而是：

```text
文档 → 切片 → 向量
问题 → 向量
向量相似度 → 找回片段
片段 + 问题 → LLM 生成回答
```

因此更新知识库通常不需要重新训练模型；只需要重新解析、向量化和写入 Milvus。

## 11. 排错练习

### 场景 A：文档一直是 `pending`

优先检查：

```text
BackgroundTasks 是否成功加入
后台任务是否抛异常
Document 是否被改成 processing
临时文件是否存在
```

### 场景 B：文档变为 `failed`

按顺序检查：

```text
DocMind Key 和 endpoint
解析任务状态
layouts 是否为空
chunk_text 是否产生切片
Embedding API 是否返回向量
Milvus 插入错误
```

### 场景 C：文档 `completed`，研究检索为空

重点检查：

```text
Milvus collection 名称
查询使用的 collection 名称
embedding 模型和维度
collection 是否 load
search_local 是否真的为 True
```

## 12. 本课练习

请回答：

1. 为什么 PostgreSQL 的 `Document(status="completed")` 不能单独证明文档可检索？
2. 文本为什么要先切片再生成向量？
3. Embedding 向量是答案吗？它的作用是什么？
4. 如果普通聊天能检索到文档，但 DeepResearch 本地搜索为空，你首先比较什么？
5. 当前代码中为什么可能出现 `kb_<知识库名称>` 和 `knowledge_base` 两个集合名？

## 13. 本课结论

RAG 的完整数据流是：

```text
上传文件
→ PostgreSQL 登记元数据
→ DocMind 解析
→ 文本切片
→ Embedding
→ Milvus 写入
→ 问题向量化
→ 相似度检索
→ DeepScout 使用证据
→ LeadWriter 写入报告
```

