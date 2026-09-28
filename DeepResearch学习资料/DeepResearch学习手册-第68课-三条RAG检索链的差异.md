# DeepResearch 学习手册·第 68 课

## 三条 RAG 检索链：普通聊天、DeepResearch 和政策搜索

项目里有多个“知识库搜索”入口。它们都可能使用 Embedding 和 Milvus，但集合名、调用方、重排方式和返回事件并不相同。

---

## 1. 普通聊天 `/chat/completion/v1`

文件：`backend/app/router/chat_router.py`。

主要顺序：

```text
用户问题
  → chat_service.retrieve_from_knowledge_base()
  → chat_service.retrieve_from_web()
  → 合并 knowledge_docs + web_docs
  → rerank_documents()
  → get_chat_completion()
  → SSE 文本回答
```

是否检索知识库和网络由请求中的：

- `search_knowledge`
- `search_web`

控制。

这条旧链路的知识库集合由 `default_dataset_id` 或旧服务配置决定，不应直接假定它等同于新知识库页面创建的 `kb_<名称>` 集合。

---

## 2. 普通聊天 `/chat/completion`

这条接口把知识库检索固定到：

```text
policy_documents
```

主要顺序：

```text
retrieve_content("policy_documents", question)
  → 转换政策文档格式
  → Web 搜索
  → 合并
  → DashScope 重排
  → LLM 流式回答
```

它更像政策文档兼容链，而不是知识库管理页面上传文档后的通用集合链。

因此同样是“打开知识库搜索”，不同聊天接口可能查的是不同集合。

---

## 3. DeepResearch 本地搜索

文件：`backend/app/service/deep_research_v2/agents/scout.py`。

当 `ResearchState.search_local == True` 时，DeepScout 会执行本地向量搜索。当前源码中它使用的集合名是固定的：

```text
knowledge_base
```

而知识库上传任务使用的是：

```text
kb_{kb_name}
```

这就形成了集成风险：

```text
页面上传成功
  → 写入 kb_某个名称

DeepResearch 本地搜索
  → 查询 knowledge_base
```

如果两个集合没有额外同步，DeepResearch 可能查不到页面刚上传的文档，即使 PostgreSQL 状态已经是 `completed`。

---

## 4. 通用 `retrieve_content()` 做什么

文件：`backend/app/service/retrieval_service.py`。

它的基本链路是：

```text
question
  → generate_embedding([question])
  → milvus.search(collection_name, query_vector, top_k, kb_id)
  → 转换为 document_id/document_name/content/score
```

`kb_id` 是可选过滤参数。如果上传时写入的值和搜索过滤值不同，可能得到空结果。

函数遇到异常时会打印堆栈并返回空列表：

```python
except Exception:
    return []
```

这会让上层看起来像“没有相关文档”，而不是明确显示 Milvus 或 Embedding 故障。

---

## 5. 三条链的对比

| 链路 | 入口 | 主要集合/数据源 | 是否重排 | 输出 |
|---|---|---|---|---|
| 普通聊天 v1 | `/chat/completion/v1` | 默认数据集 + Web | 是 | 普通聊天 SSE |
| 普通聊天 v2 | `/chat/completion` | `policy_documents` + Web | 是 | 普通聊天 SSE |
| DeepResearch 本地搜索 | `/research/stream` V2 | 当前固定 `knowledge_base` | 由研究流程继续分析 | `search_results` 等研究事件 |

它们不能因为都使用 Milvus，就被当作同一条 RAG 链。

---

## 6. 一次“检索为空”的证据顺序

遇到页面没有本地结果时，按以下顺序：

1. 确认实际调用的是哪个 HTTP 接口。
2. 确认该接口使用的集合名。
3. 确认 Embedding 是否返回向量。
4. 确认 Milvus 集合是否存在、是否有实体。
5. 确认 `kb_id` 过滤值是否匹配写入值。
6. 查看检索函数是否捕获异常并降级为空数组。
7. 最后查看前端是否正确渲染返回事件。

如果是 DeepResearch，还要确认 `search_local` 是否真的从 `search_modes` 传到了 `ResearchState`。

---

## 7. 工程改进方向

为了避免三条链路互相找不到数据，可以：

1. 用知识库 UUID 生成稳定集合名。
2. 在 `KnowledgeBase` 或配置中显式保存 collection_name。
3. 上传、删除、切片查询、普通聊天和 DeepResearch 全部读取同一字段。
4. 检索异常返回结构化错误，而不是静默返回 `[]`。
5. 在响应中带上 collection_name、top_k、过滤条件和检索耗时，便于排错。
6. 为“上传后 DeepResearch 能召回”增加真实集成测试。

---

## 练习

场景：知识库页面显示文档已完成，普通聊天能查到内容，但 DeepResearch 选择本地搜索时没有结果。

请判断最优先检查什么。参考方向：先比较普通聊天实际使用的集合和 DeepScout 使用的集合；项目当前普通聊天可能查默认数据集或 `policy_documents`，而 DeepScout 使用固定 `knowledge_base`，集合不一致比前端渲染更值得优先排查。

