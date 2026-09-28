# DeepResearch 学习手册·第 116 课：从源码跟读一次研究请求

## 本课目标

本课不再只背“六个 Agent”这些名称，而是沿着一个真实问题，逐层确认：

```text
React 点击发送
→ 前端 API
→ FastAPI Router
→ DeepResearchV2Service
→ ResearchState
→ _run_simplified()
→ 六个 Agent
→ SSE 事件
→ ReadableStream
→ React 研究详情和报告
```

示例问题：

```text
分析新能源汽车行业未来三年的竞争格局
```

## 1. 前端发出请求

文件：`frontend/src/api/session.ts`

函数：`deepsearch(params, options)`。

它向 `/research/stream` 发送 `POST` 请求，并设置：

```text
Accept: text/event-stream
responseType: stream
adapter: fetch
```

这说明前端期待的是流，而不是一次性 JSON。请求参数主要包括：

```text
query
session_id
search_modes
```

在聊天页面中，`frontend/src/pages/chat/index.tsx` 调用这个函数，然后通过 `ReadableStream` reader 持续读取响应。页面不是研究结果的生产者，它负责发起请求、解析事件、更新 React 状态并渲染结果。

## 2. Router 选择版本

文件：`backend/app/router/research_router.py`

请求模型 `ResearchRequest` 的 `version` 默认值是 `v2`。因此前端通过 POST 发送、又没有显式传 `version` 时，Router 进入：

```python
service_v2 = get_research_service_v2()
service_v2.research(...)
```

然后用 `StreamingResponse` 返回，媒体类型是 `text/event-stream`。

同一个文件里，GET `/research/stream` 的 `version` 默认值是 `v1`。所以不能只看到路径相同就断言 GET 和 POST 走同一条链。

## 3. Service 进入 Graph

文件：`backend/app/service/deep_research_v2/service.py`

`DeepResearchV2Service.research()` 会在没有 `session_id` 时创建 UUID，然后调用：

```python
async for event in self.graph.run(
    query, session_id,
    resume=resume,
    user_id=user_id,
    search_web=search_web,
    search_local=search_local
):
    yield self._format_sse(event)
```

`_format_sse()` 把事件字典包装成：

```text
data: {JSON}\n\n
```

研究结束后还会发送：

```text
data: [DONE]\n\n
```

## 4. Graph 创建或恢复共享状态

文件：`backend/app/service/deep_research_v2/graph.py` 和 `state.py`

如果没有可加载的检查点，`create_initial_state()` 创建 `ResearchState`。它不是数据库，而是一次研究执行期间所有 Agent 共享的内存状态。关键字段包括：

| 阶段 | 主要字段 |
|---|---|
| 规划 | `outline`、`research_questions`、`hypotheses` |
| 搜索 | `facts`、`raw_sources`、`data_points` |
| 分析 | `charts`、`code_executions`、`insights` |
| 写作 | `draft_sections`、`final_report`、`references` |
| 审核 | `critic_feedback`、`unresolved_issues`、`quality_score` |

`graph.run()` 当前明确进入 `_run_simplified(state)`。文件中的 LangGraph `astream()` 分支存在，但被注释掉，没有作为默认执行路径。

## 5. 六个 Agent 如何接力

当前简化执行器的主要顺序是：

```text
ChiefArchitect
→ DeepScout
→ DataAnalyst
→ CodeWizard
→ LeadWriter
→ CriticMaster
```

它们通过同一个 `state` 交接，不是通过互相直接调用传递返回值。

| Agent | 读取重点 | 写入重点 | 典型事件 |
|---|---|---|---|
| `ChiefArchitect` | `query` | `outline`、研究问题 | 规划/思考事件 |
| `DeepScout` | `outline`、搜索开关 | `facts`、来源、数据点 | 搜索结果/观察事件 |
| `DataAnalyst` | `data_points`、事实 | 洞察、ECharts 配置 | `chart`、分析事件 |
| `CodeWizard` | 数据点和大纲 | `code_executions`、PNG 图表 | `code_result`、`chart` |
| `LeadWriter` | 大纲、事实、洞察、来源 | 章节草稿、最终报告 | `section_content`、`report_draft` |
| `CriticMaster` | 报告、证据 | 反馈、质量分、待补搜索 | `review`、修订事件 |

`CriticMaster` 发现严重问题时，执行器可能再次调用搜索和写作；因此“六个 Agent 各调用一次”不是所有请求的绝对规则。

## 6. 为什么能实时显示

`_run_simplified()` 为一次研究建立 `asyncio.Queue`，并把它放入状态。执行一个 Agent 的同时，Graph 从队列取出 Agent 发出的消息并 `yield` 给 Service。Service 格式化成 SSE，浏览器 reader 收到字节片段后先放入 buffer，拼出完整的 `data: ...\n\n` 块，再解析 JSON。

网络分块可能把一个 JSON 拆成两次甚至多次读取，所以不能对每次 `reader.read()` 的结果直接 `JSON.parse()`。

## 7. 前端如何处理完成事件

文件：`frontend/src/pages/chat/index.tsx`

收到 `research_complete` 后，页面会：

1. 把 `final_report` 写入聊天消息内容。
2. 写入研究详情中的 `streamingReport`。
3. 把参考文献映射到前端来源结构。
4. 把研究步骤标记为完成。
5. 触发 React 重新渲染。

因此最终报告显示依赖四件事同时成立：后端状态有报告、后端发送完成事件、前端正确拼接并解析 SSE、React 状态更新成功。

## 8. 本课必须记住的边界

1. `ResearchState` 是一次执行的共享工作台，不等于 PostgreSQL。
2. SSE 是服务器向浏览器持续推送的单向事件流，不等于 WebSocket。
3. `POST /research/stream` 默认 V2，GET 同路径默认 V1；仍应以实际参数为准。
4. V2 当前默认是手写 `_run_simplified()`，不是 LangGraph 的 `astream()`。
5. `resume=True` 会尝试载入旧状态，但当前执行器仍从手写流程入口继续，不能直接称为严格节点级续跑。
6. 静态源码、Python 编译和前端构建不能证明真实 LLM、数据库、Milvus 和搜索 API 已经联通。

## 9. 四题验收

请用自己的话回答，每题 3 至 8 行，并至少写一个文件或函数名。

### 题 1：完整主链路

用户输入上面的示例问题后，依次写出前端函数、HTTP 方法和路径、Router、Service、执行器、共享状态、SSE 和最终前端展示。

### 题 2：三个核心对象

分别解释 `ResearchState`、SSE、React 研究详情页面的职责。特别说明它们分别不负责什么。

### 题 3：状态演化

规划完成、搜索完成、写作完成时，分别指出 `outline`、`facts`、`data_points`、`charts`、`draft_sections`、`final_report` 应处于什么状态。

### 题 4：版本判断

判断并说明理由：

```text
A. POST /research/stream 默认进入 V2。
B. V2 当前默认执行 LangGraph astream()。
C. 只给 state['final_report'] 赋值，前端一定能显示报告。
D. SSE 的每个网络读取片段都可以直接 JSON.parse()。
```

## 10. 下一步

完成四题后，再进入“CodeWizard + RAG + 检查点”的综合故障排查。未完成验收前，不进入大厂面试模拟，因为面试问题需要建立在你能独立追踪源码的基础上。
