# DeepResearch 学习手册：第 83 课

## RAG：从上传文档到 DeepScout 召回

RAG 可以先理解成四步：把文档切成小块，把小块变成向量，保存到向量数据库，提问时用问题向量找相似小块。这个项目里，RAG 不是单独一个函数，而是一条跨越上传接口、后台任务、DocMind、Embedding、Milvus 和 DeepScout 的链路。

## 1. 上传阶段：先保存元数据

文件：`backend/app/router/knowledge_router.py`

用户上传文件后，接口先做：

```text
验证知识库属于当前用户
验证文件类型
保存临时文件
创建 PostgreSQL Document 记录
设置 status = pending
提交 BackgroundTasks
返回“正在后台处理”
```

因此上传接口返回成功，不代表文件已经完成向量化。此时 PostgreSQL 主要保存文档的身份和处理状态，例如文件名、知识库 ID、用户 ID、路径和 `status`。

## 2. 后台处理：Document 状态变化

后台任务 `process_document()` 大致经历：

```text
pending
  -> processing
  -> completed
或 failed
```

它会打开文件，调用 `DocMindService`，并在成功或异常时更新 Document 状态。前端通过文档列表或状态接口轮询，直到看到 completed 或 failed。

## 3. DocMind 和切片

文件：`backend/app/service/docmind_service.py`

后台处理先向 DocMind 提交解析任务，再等待任务完成，收集文本。拿到完整文本后调用 `chunk_text()` 切成多个片段。

切片的原因是：

- 整个文件太长，不能直接一次放进检索提示词。
- 向量检索需要比较较小的语义单元。
- 最终召回时可以只取与问题最相关的片段。

每个片段会带有文件名、片段序号、文档 ID 和文本内容。

## 4. Embedding 和 Milvus

每个文本片段交给 `generate_embedding()` 生成向量。之后构造 Milvus 文档：

```text
id
doc_id
kb_id
filename
content
chunk_index
vector
```

然后调用 `milvus.insert_documents(index_name, documents)` 写入向量集合。PostgreSQL 记录“这个文档处理到什么状态”；Milvus 保存真正用于相似度搜索的片段和向量。两者职责不同。

## 5. 集合名称是当前最重要的排错点

上传处理代码使用：

```python
index_name = f"kb_{kb_name}".lower().replace(" ", "_")
```

例如知识库名称是 `Finance Reports`，写入集合可能是：

```text
kb_finance_reports
```

但是 DeepResearch 的 `DeepScout._execute_local_search()` 当前调用 Milvus 时固定使用：

```python
collection_name = "knowledge_base"
```

这意味着：即使 PostgreSQL 中 Document 已经是 `completed`，上传链实际写入的集合也可能和 DeepScout 查询的集合不同，最终本地搜索返回空列表。

这是源码层面已经能确认的实现风险，不需要先猜 Milvus 本身坏了。

## 6. DeepScout 本地召回

文件：`backend/app/service/deep_research_v2/agents/scout.py`

当 `ResearchRequest.search_modes` 包含 `local` 时，路由传入 `search_local=True`。DeepScout 会：

```text
问题文本
  -> generate_embedding(query)
  -> Milvus.search("knowledge_base", query_vector, top_k)
  -> 把结果格式化为统一搜索结果
  -> 继续交给 LLM 分析
  -> 形成 facts、data_points、references
```

返回给 DeepScout 的本地片段会被包装为 `local://kb/...` URL，并标记 `is_local=True`。之后它们和网络搜索结果一起进入事实提取与报告写作。

## 7. 为什么三种状态不能混为一谈

### 上传接口成功

只证明文件已经被接收、数据库记录已经创建，并且后台任务已经提交。

### Document = completed

说明后台任务认为 DocMind、切片、Embedding 和 Milvus 写入流程成功结束，但还不能单独证明 DeepResearch 会查询正确的集合。

### DeepScout 返回本地结果

这才说明“当前问题的向量”确实在 DeepScout 查询的集合中找到了结果，并且结果经过了格式转换。

## 8. 普通聊天和 DeepResearch 不一定走同一条 RAG 链

普通聊天可能调用 `retrieval_service.retrieve_from_knowledge_base()`，它根据 `kb_name` 计算集合名：

```python
f"kb_{kb_name}".lower().replace(" ", "_")
```

DeepResearch 的本地分支则固定查询 `knowledge_base`。因此可能出现：

```text
普通聊天能检索到
DeepResearch 检索不到
```

遇到这种情况，先比较调用路径、集合名称、Embedding 模型和 top_k，再检查前端开关。不要只看 Document 状态。

## 9. RAG 故障排查顺序

```text
1. Document 是否存在，用户和知识库是否匹配
2. status 是否从 pending 变成 processing、completed 或 failed
3. DocMind 是否返回非空文本
4. 切片数量是否大于 0
5. Embedding 数量是否和切片数量一致
6. 实际写入的 Milvus 集合名是什么
7. DeepScout 实际查询的集合名是什么
8. 查询向量是否生成成功
9. Milvus.search 是否报错或返回空列表
10. 返回结果是否进入 facts 和 search_results 事件
```

## 10. 本课练习

请回答：

> 为什么“Document.status = completed”仍然不能证明 DeepResearch 一定能召回这篇文档？

最低合格答案必须提到：写入集合名、查询集合名、Milvus 检索三者需要一致。
