# DeepResearch 学习手册·第 64 课

## 研究接口契约：请求字段、版本选择和 SSE 事件

工程问题经常不是某个函数完全错误，而是调用方和被调用方对字段含义理解不一致。本课专门看 `/research/stream` 的契约。

---

## 1. `ResearchRequest` 的字段

文件：`backend/app/router/research_router.py`。

当前请求模型包含：

| 字段 | 含义 | 默认/兼容说明 |
|---|---|---|
| `query` | 用户研究问题 | 必填 |
| `session_id` | 会话和检查点标识 | 可选 |
| `max_iterations` | V1 迭代次数 | 默认 3，V2 不一定直接使用此字段 |
| `kb_name` | 本地知识库名称 | 可选 |
| `search_web` | 旧版网络搜索开关 | 兼容字段 |
| `search_local` | 旧版本地搜索开关 | 兼容字段 |
| `search_modes` | 新版搜索模式列表 | 可传 `web`、`local` |
| `version` | 研究实现版本 | 默认 `v2` |

重要边界：`search_modes` 一旦不为 `None`，会优先于旧的 `search_web` 和 `search_local`。

例如：

```json
{
  "query": "分析新能源汽车行业",
  "search_web": true,
  "search_local": true,
  "search_modes": ["web"]
}
```

实际结果是 `search_web=true`、`search_local=false`，因为新版列表优先。

---

## 2. POST 和 GET 不是同一条契约

当前项目保留两类入口：

```text
POST /research/stream
  ResearchRequest
  默认 version=v2

GET /research/stream
  Query 参数
  默认 version=v1
```

因此不能只看到路径相同，就认为两次请求会进入相同的 Agent 链路。排查时至少记录：

```text
HTTP 方法
请求体或 Query 参数
version
响应 Content-Type
第一条 SSE 事件
```

---

## 3. V2 事件的两次包装

V2 Agent 先往 `ResearchState` 中的消息队列写入事件，例如：

```python
{
    "type": "research_step",
    "content": {...}
}
```

`DeepResearchV2Service._format_sse()` 再把它变成：

```text
data: {"type":"research_step","content":{...}}\n\n
```

这中间有两个不同的数据层：

1. Python 字典：后端 Agent 和 Graph 使用。
2. SSE 文本：浏览器网络层和前端解析器使用。

如果后端日志显示字典正确，但浏览器收到的文本格式错误，问题可能发生在序列化或 SSE 包装，而不是 Agent。

---

## 4. 前端事件解析契约

前端读取 `ReadableStream` 后，把文本放入临时缓冲区，按换行找到 `data: ` 行，再去掉前缀并执行 `JSON.parse()`。

V2 常见事件被映射到：

```text
research_start
  → 初始化研究过程

research_step
  → 创建/更新步骤和统计

search_results
  → detail.searchResults

knowledge_graph
  → detail.knowledgeGraph

charts / chart
  → detail.charts

research_complete
  → detail.streamingReport
```

事件名、字段名或 `content` 层级不一致时，后端可能“成功发出事件”，但页面看起来像没有数据。

---

## 5. 一个字段的完整追踪：`search_modes`

```text
前端 deviceState.searchModes
  → deepsearch({ search_modes })
  → ResearchRequest.search_modes
  → get_search_web()/get_search_local()
  → DeepResearchV2Service.research(search_web, search_local)
  → ResearchGraph.run(...)
  → ResearchState.search_web/search_local
  → DeepScout 判断是否调用网络或本地检索
```

这条链中任何一处字段名错误，都可能导致“界面选择了本地知识库，但后端没有检索本地库”。

---

## 6. 一个字段的完整追踪：`session_id`

```text
前端会话 ID
  → ResearchRequest.session_id
  → V2 Service；没有时生成 UUID
  → ResearchState.session_id
  → Redis 取消 key
  → ResearchCheckpoint.session_id
  → 刷新页面时查询 checkpoint
```

`session_id` 在研究流程中承担身份关联、取消和恢复作用，但当前研究 Router 没有显式注入必需用户依赖，因此不能只凭它证明用户授权关系。

---

## 7. 接口契约排错方法

遇到“参数明明传了但行为不对”，按以下顺序查：

1. 浏览器 Request Payload。
2. Pydantic `ResearchRequest` 字段和默认值。
3. Router 里的转换函数。
4. Service 调用参数名。
5. `ResearchState` 初始值。
6. Agent 读取字段的条件分支。
7. SSE 中是否把结果发出来。
8. React 是否处理该事件。

这比只搜索字段名更可靠，因为同一个概念可能在不同层使用不同命名，例如 `search_modes`、`search_web` 和 `search_local`。

---

## 练习

用户在界面选择“仅本地知识库”，但后端日志显示 `search_web=True, search_local=False`。请判断：

1. 应先查 Agent，还是先查请求契约？
2. 哪个字段优先级可能导致这个结果？
3. 你会查看哪两个源码位置？

参考答案：先查请求契约；`search_modes` 优先于旧的 `search_web/search_local`，应查看前端 `deepsearch()` 调用处和后端 `ResearchRequest.get_search_web()/get_search_local()`。

