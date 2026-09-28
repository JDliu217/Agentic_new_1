# DeepResearch 学习手册·第 60 课

## 一次研究请求的工程排错方法

这一课解决一个实际问题：用户点击“开始研究”后没有结果，应该从哪里开始查？

排错不是先猜某个 Agent 写错了，而是沿着请求实际经过的边界逐层收集证据。

---

## 1. 先确认前端是否真的发出了请求

研究入口在：

```text
frontend/src/pages/chat/index.tsx
  → api.session.deepsearch()
  → POST /research/stream
```

第一步打开浏览器开发者工具的 Network 面板，检查：

- 请求 URL 是否是 `/research/stream`。
- 方法是否是 `POST`。
- 请求体是否包含 `query`、`session_id` 和 `search_modes`。
- 是否带有 JWT Authorization 请求头。
- 响应的 Content-Type 是否是 `text/event-stream`。
- 请求是否在发送前就返回 401、422 或 500。

如果 Network 中没有请求，问题在前端按钮、模式判断或事件处理；如果有请求但立即返回 HTTP 错误，先不要进入 Agent 排查。

---

## 2. 再确认 FastAPI 路由是否接住请求

后端入口是：

```text
backend/app/router/research_router.py
```

这里负责请求参数、用户身份、会话关系、版本选择和流式响应包装。要区分：

```text
HTTP 401：认证/JWT 问题
HTTP 404：路径或路由注册问题
HTTP 422：请求字段不符合 Schema
HTTP 500：后端处理过程中抛出异常
HTTP 200 但无事件：异步生成器、外部依赖或前端解析问题
```

`POST /research/stream` 默认选择 V2；`GET /research/stream` 是另一条 V1 入口。排错时必须先确认 HTTP 方法，不能只看 URL 文本。

---

## 3. 确认 V2 是否进入真实执行流程

V2 主要文件：

```text
backend/app/service/deep_research_v2/service.py
backend/app/service/deep_research_v2/graph.py
```

当前默认调用关系是：

```text
DeepResearchV2Service
  → DeepResearchGraph.run()
  → _run_simplified()
  → 六个 Agent
```

不要因为项目中存在 LangGraph 节点定义，就假定请求已经通过 LangGraph 图执行。判断真实路径要看 `run()` 当前实际调用的分支和日志。

最先应该找的运行证据包括：

- 是否创建了 `ResearchState`。
- 是否进入 planning 阶段。
- 是否创建 `ChiefArchitect`、`DeepScout`、`DataAnalyst`、`CodeWizard`、`LeadWriter`、`CriticMaster`。
- 是否出现 Agent 消息或 `phase` 事件。

---

## 4. SSE 没有内容时如何定位

V2 的简化执行器使用 `asyncio.Queue` 收集 Agent 的实时消息，再由 Service 转成 SSE：

```text
Agent 产生消息
  → asyncio.Queue
  → DeepResearchGraph 读取
  → DeepResearchV2Service 格式化
  → data: {...}\n\n
  → 浏览器 ReadableStream
```

要区分三个故障：

1. Agent 没有产生消息：看 Agent、LLM 或工具调用。
2. 后端产生了消息但浏览器没有收到：看生成器、响应头和网络连接。
3. 浏览器收到了原始字节但页面不更新：看前端缓冲区、换行切分和事件类型映射。

前端不能假定每次 `reader.read()` 都返回完整的一条 SSE。代码需要把分片拼进缓冲区，按空行拆分事件；一条 JSON 可能跨多个网络分片。

---

## 5. 按事件判断故障位置

前端主要处理这些事件：

| 事件 | 说明 | 常见排错位置 |
|---|---|---|
| `research_step` | 创建或更新研究步骤 | Agent 阶段消息、步骤类型映射 |
| `search_results` | 写入搜索结果 | Web 搜索、本地知识库、结果格式 |
| `knowledge_graph` | 写入图谱 | DataAnalyst 或图谱解析 |
| `charts` | 批量写入图表 | DataAnalyst、CodeWizard、状态聚合 |
| `chart` | 单个图表事件 | 图表生成器、事件兼容路径 |
| `research_complete` | 写入报告并结束 | LeadWriter、CriticMaster、最终状态 |
| `research_cancelled` | 协作式取消 | Redis 标志和检查时机 |
| `error` | 后端异常转成事件 | 具体阶段日志和异常堆栈 |

例如：

- 有 `research_step`，没有 `search_results`：优先查 DeepScout 或搜索服务。
- 有 facts，但 `charts` 为空：优先查 DataAnalyst/CodeWizard 输出和图表事件，不要先查 ECharts。
- 有 `charts` 事件，但页面没有图：查前端 `researchDetailsRef`、`researchDataVersion` 和 Visualization 组件。
- 有报告但刷新后消失：查检查点 `ui_state_json` 和前端恢复映射。

---

## 6. 外部依赖的排错顺序

一次研究可能依赖：

```text
LLM
Web 搜索
Embedding
Milvus
PostgreSQL
Redis
DocMind
```

建议顺序：

1. 先确认后端进程能访问。
2. 再确认 PostgreSQL 和 Redis。
3. 再确认 Milvus 和 Embedding 服务。
4. 再确认外部搜索 API 和 LLM Key。
5. 最后判断某个 Agent 的业务逻辑。

原因是基础设施未就绪时，Agent 失败只是结果，不是根因。

当前项目中 `/hello` 只能证明 FastAPI 路由可访问，不能证明数据库、Redis、Milvus 或 LLM 已就绪。

---

## 7. 取消和恢复的排错边界

取消请求：

```text
POST /research/cancel/{session_id}
  → Redis 写入 research:cancel:{session_id}
  → Graph 在阶段边界检查
  → 发出 research_cancelled
```

这是协作式取消。它不会强行杀死已经发出的外部 HTTP 请求，也不保证点击取消后进程立刻停止。

刷新页面时，前端需要区分：

- `/sessions/{id}`：恢复会话消息。
- `/research/checkpoint/{id}/full`：恢复研究步骤、搜索结果、图表、图谱和报告。

当前 `resume=True` 会载入旧状态，但简化执行器仍从规划入口重新执行，因此不能把它描述成精确的节点级断点续跑。

---

## 8. 一张最小排错表

| 现象 | 第一条证据 | 下一步 |
|---|---|---|
| 页面按钮无反应 | 浏览器 Console/Network | 查前端事件和模式状态 |
| 401 | 响应体和 localStorage Token | 查登录、JWT、Axios 请求头 |
| 422 | 请求 JSON 与 Pydantic 字段 | 查 `query/session_id/search_modes` |
| 500 且无 SSE | FastAPI 堆栈 | 查路由、数据库、配置导入 |
| 有 SSE 但无搜索结果 | 后端 Agent 日志 | 查 DeepScout、搜索 API、Milvus |
| 有结果但无图表 | `charts`/`chart` 事件 | 查分析、代码执行、前端状态 |
| 刷新后研究详情空白 | checkpoint full 响应 | 查 `ui_state_json` 和恢复映射 |
| 只有演示数据 | Text2SQL 日志和数据库连接 | 查是否走 `_get_mock_data()` |

---

## 9. 本课要形成的工程习惯

每次排错都记录四件事：

```text
现象：用户实际看到什么
证据：哪一个请求、日志、事件或数据库记录证明了什么
定位：问题属于哪一层
下一步：还需要收集哪条证据
```

不要把“容器 running”“接口返回 200”“页面显示了 mock 数据”直接等同于完整功能可用。

---

## 练习

假设页面显示“研究进行中”，Network 中能看到多个 `research_step`，但一直没有 `search_results`，最后收到 `error`。请回答：

1. 当前能证明请求已经经过哪些层？
2. 你下一步先查前端 SSE 解析，还是查 DeepScout/搜索服务？
3. 为什么？

参考方向：至少证明了前端请求、FastAPI 流式响应和部分 V2 阶段事件已连通；优先查 DeepScout、Web 搜索、知识库检索及对应外部依赖，因为前端已经能解析 `research_step`，问题更可能发生在搜索阶段。

