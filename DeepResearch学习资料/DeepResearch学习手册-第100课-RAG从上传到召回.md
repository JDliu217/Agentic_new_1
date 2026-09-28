# DeepResearch 学习手册：第 100 课

## RAG：从上传文档到 DeepScout 召回

RAG 的全称是 Retrieval-Augmented Generation，意思是：先从外部知识中检索相关内容，再把这些内容交给 LLM 生成答案。

在这个项目中，知识库链路可以拆成“管理记录”和“向量检索”两部分。

## 1. 上传接口先写 PostgreSQL

源码：

```text
backend/app/router/knowledge_router.py
```

上传文档时，接口先完成：

```text
验证用户和知识库归属
→ 保存临时文件
→ 创建 Document 记录
→ status = pending
→ 提交 BackgroundTasks
→ 立即返回
```

PostgreSQL 中的 `Document` 主要保存：

```text
文档 ID、知识库 ID、用户 ID、文件名、文件类型、文件大小、文件路径、处理状态、切片数量、错误信息
```

这里的 `pending` 只表示任务已经登记，不表示文本已经能被搜索。

## 2. 后台任务进入 processing

后台函数：

```text
process_document()
```

它先把状态改成：

```text
processing
```

然后调用：

```text
process_document_with_docmind()
```

## 3. DocMind 解析文件

源码：

```text
backend/app/service/docmind_service.py
```

DocMind 链路是：

```text
提交文件解析任务
→ 轮询任务状态
→ 获取布局结果
→ 提取 markdown/text
→ 合并成完整文本
```

如果解析失败、超时或内容为空，处理结果返回失败，`Document.status` 会变为：

```text
failed
```

## 4. 文本切片

默认参数：

```text
chunk_size = 500
overlap = 50
```

切片不是简单地每 500 个字符硬切，代码会尝试在句号、问号、感叹号或换行处结束当前片段。

重叠的作用是：相邻片段共享一部分上下文，减少重要句子刚好被切断后无法召回的问题。

## 5. Embedding 把文本变成向量

源码：

```text
backend/app/service/embedding_service.py
```

Embedding 模型默认是：

```text
text-embedding-v4
```

默认向量维度是：

```text
1024
```

一个文本片段会从字符串变成类似这样的数字数组：

```text
[0.012, -0.083, 0.221, ...]
```

这个数组不是文章内容，而是语义特征表示。相似问题和相似片段的向量通常距离更近。

## 6. Milvus 保存向量和切片

源码：

```text
backend/app/service/milvus_service.py
```

每条 Milvus 记录同时保存：

```text
向量
文档 ID
知识库 ID
文件名
切片文本
切片序号
```

集合使用 COSINE 相似度和 IVF_FLAT 索引。

这就是为什么 PostgreSQL 和 Milvus 都需要保存文档相关信息：

```text
PostgreSQL：业务状态和权限元数据
Milvus：语义检索所需的向量和切片
```

## 7. 文档状态变为 completed

Milvus 写入成功后，后台任务把 PostgreSQL 记录更新为：

```text
completed
```

但要注意：代码当前把这个状态更新和向量写入结果绑定在处理函数的成功返回上；排错时仍应检查 Milvus 集合是否存在、实体数量是否增加，以及查询是否真的命中。

## 8. DeepScout 查询本地知识库

源码：

```text
backend/app/service/deep_research_v2/agents/scout.py
```

本地搜索流程：

```text
用户问题或章节查询
→ generate_embedding(query)
→ Milvus search
→ COSINE Top-K
→ 格式化成 local result
→ 加入搜索结果和事实分析链
```

当前 DeepScout 的本地搜索使用固定集合名：

```text
knowledge_base
```

而知识库上传后台使用：

```text
kb_<知识库名称>
```

这构成一个重要的集成风险：文档可能已经在 `Document` 中显示 `completed`，也已经写入 `kb_xxx`，但 DeepScout 查询 `knowledge_base` 时仍然查不到。

## 9. 为什么“上传成功”不等于“能召回”

必须区分多个状态：

```text
HTTP 上传成功
→ Document = pending
→ Document = processing
→ DocMind 解析成功
→ Embedding 成功
→ Milvus 写入成功
→ Document = completed
→ 查询集合正确
→ 查询向量生成成功
→ Top-K 返回有效切片
```

其中任何一步失败，都可能造成“页面显示文档存在，但研究没有使用它”。

## 10. 排错顺序

```text
1. PostgreSQL Document.status
2. 后台任务日志
3. DocMind task_id 和最终状态
4. chunks 数量
5. Embedding 返回数量和维度
6. Milvus 集合名称和实体数量
7. DeepScout 实际查询的集合名称
8. query embedding 是否成功
9. search 返回数量和 score
10. facts 是否写入 ResearchState
```

## 11. 修复集合命名风险的方向

推荐让一个稳定的知识库标识贯穿全链路：

```text
collection_name = f"kb_{knowledge_base_id}"
```

上传、查看切片、删除文档和 DeepScout 搜索都使用同一规则。不要依赖可修改的知识库名称，也不要在 Agent 中写死集合名。

## 12. 本课练习

1. PostgreSQL 和 Milvus 在 RAG 中分别保存什么？
2. 为什么 `Document.status == "completed"` 仍不能证明 DeepScout 一定能召回？
3. 从上传到召回，哪一步把文本转换成 1024 维向量？
4. 当前项目的集合命名风险是什么？你会如何修复？
