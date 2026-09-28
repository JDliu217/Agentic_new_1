# DeepResearch 学习手册：第 80 课

## 主链路逐层阅读：从点击发送到页面显示

这一课只追踪一个动作：用户在 DeepResearch 页面输入问题并点击发送。目标是建立一条可以自己复述、定位源码、排查故障的主线。

## 1. 先记住项目的真实主链路

```text
React 聊天页
  -> deepsearch()
  -> POST /research/stream
  -> research_router.stream_research()
  -> DeepResearchV2Service.research()
  -> DeepResearchGraph.run()
  -> _run_simplified()
  -> ChiefArchitect
  -> DeepScout
  -> DataAnalyst
  -> CodeWizard
  -> LeadWriter
  -> CriticMaster
  -> SSE data: {...}
  -> ReadableStream
  -> React 研究步骤、来源、图表和报告
```

这条链路是当前代码的实际默认路径。项目中虽然保留了 LangGraph 构图代码，但 `run()` 当前直接调用 `_run_simplified()`，因此不能只根据类名或注释判断运行路径。

## 2. 第一层：React 决定发什么请求

文件：`frontend/src/pages/chat/index.tsx`

`sendChat()` 根据当前聊天类型分支。Deepsearch 类型会调用：

```ts
api.session.deepsearch({
  query: message,
  session_id: id,
  search_modes: deviceState.searchModes as string[],
})
```

这里的三个重要输入是：

| 字段 | 作用 |
|---|---|
| `query` | 用户真正提出的问题 |
| `session_id` | 让后端能保存检查点、取消任务和恢复页面状态 |
| `search_modes` | 选择网络搜索、知识库搜索或两者 |

文件：`frontend/src/api/session.ts`

`deepsearch()` 使用 `POST /research/stream`，并设置 `Accept: text/event-stream`、`responseType: stream` 和 Fetch 适配器。它得到的不是普通 JSON，而是一个可持续读取的 `ReadableStream`。

## 3. 第二层：FastAPI 路由选择 V1 或 V2

文件：`backend/app/router/research_router.py`

`ResearchRequest` 会接收并校验请求。POST 的 `version` 默认值是 `v2`，所以前端没有显式传版本时，通常进入 V2：

```python
if request.version == "v2":
    service_v2 = get_research_service_v2()
```

路由把 `search_modes` 转换为两个布尔值：

```text
search_web
search_local
```

随后返回 `StreamingResponse`。它的生成器逐个读取服务产生的事件，并把每个事件包装成 SSE：

```text
data: {"type": "...", ...}\n\n
```

补充边界：GET `/research/stream` 的默认 `version` 是 `v1`，所以 GET 和 POST 的默认版本并不相同。

## 4. 第三层：V2 服务负责组装和格式转换

文件：`backend/app/service/deep_research_v2/service.py`

`DeepResearchV2Service.research()` 做四件事：

1. 没有 `session_id` 时生成 UUID。
2. 调用 `self.graph.run(...)`。
3. 把 Graph 产生的事件转换为 SSE 字符串。
4. 最后发送 `data: [DONE]\n\n`。

它本身不负责决定六个 Agent 的先后顺序。顺序在 `DeepResearchGraph` 中。

## 5. 第四层：Graph 创建或恢复 ResearchState

文件：`backend/app/service/deep_research_v2/graph.py`

`run()` 首先检查 `resume=True` 是否能从检查点加载状态。没有可用检查点时调用：

```python
create_initial_state(query, session_id, search_web, search_local)
```

初始状态随后被放入 `ResearchState`。可以把它理解成所有 Agent 共用的一块结构化工作台，而不是六个 Agent 之间靠自然语言私聊。

状态中最重要的字段可以按产物理解：

| 字段 | 谁主要写入 | 后面谁使用 |
|---|---|---|
| `outline` | ChiefArchitect | DeepScout、LeadWriter |
| `raw_sources` | DeepScout | 后续分析和写作 |
| `facts` | DeepScout | 引用、搜索结果和报告 |
| `data_points` | DeepScout、DataAnalyst | CodeWizard、LeadWriter |
| `charts` | DataAnalyst、CodeWizard | 前端和报告 |
| `code_executions` | CodeWizard | 调试、审计和前端统计 |
| `draft_sections` | LeadWriter | CriticMaster |
| `final_report` | LeadWriter | CriticMaster、前端 |
| `critic_feedback` | CriticMaster | Writer 或补充搜索 |

## 6. 第五层：当前真实执行是手写简化流程

`run()` 中明确把 LangGraph 执行分支注释掉，并调用：

```python
async for event in self._run_simplified(state):
    yield event
```

`_run_simplified()` 建立一个 `asyncio.Queue`。Agent 执行时把中间消息放入队列，Graph 一边等待 Agent，一边把队列消息 yield 给上层。因此前端可以实时看到过程。

当前顺序如下：

### 6.1 规划

发送 `phase=planning`，执行 `ChiefArchitect`。它根据问题生成研究大纲、子问题、关键实体和研究假设。

### 6.2 搜索

发送 `phase=researching`，执行 `DeepScout`。它根据大纲调用网络搜索，必要时调用本地知识库，把结果整理成来源和结构化事实。

### 6.3 分析

发送 `phase=analyzing`，先执行 `DataAnalyst`，再执行 `CodeWizard`。

`DataAnalyst` 偏向结构化分析和 ECharts 配置；`CodeWizard` 偏向生成 Python、执行 Python、产生图片和执行记录。两者都处于分析阶段，但职责不同。

### 6.4 写作

发送 `phase=writing`，执行 `LeadWriter`，把大纲、事实、数据和图表组织成报告。

### 6.5 审核与修订

发送 `phase=reviewing`，执行 `CriticMaster`。根据反馈，流程可能：

```text
完成
或补充搜索 -> 重新写作
或直接修订 -> 再次写作
```

循环受 `max_iterations` 限制。

## 7. 第六层：事件怎样到达前端

后端事件至少有两类：

```text
阶段事件：research_start、phase、research_complete
产物事件：research_step、search_results、knowledge_graph、charts、chart、report_chunk
```

服务层把事件写成 SSE。浏览器端的 `read(reader)` 不假定一次 `reader.read()` 就得到完整事件，因为网络分块可能把一条事件拆成多块，也可能一次得到多条事件。前端把数据先放入 `temp`，按换行取出 `data: ` 行，再调用 `JSON.parse()`。

例如，前端收到 `charts` 后，会把图表放入分析步骤详情，也会追加到当前聊天项；收到 `search_results` 后，会更新搜索步骤的来源列表；收到 `research_complete` 后，报告和统计信息进入最终展示。

## 8. 当前实现和设计意图要分开

### 源码已经确认的事实

- POST `/research/stream` 默认走 V2。
- V2 `run()` 当前调用 `_run_simplified()`。
- `ResearchState` 是 Agent 共享状态。
- 分析阶段依次调用 `DataAnalyst` 和 `CodeWizard`。
- 前端使用 `ReadableStream` 解析 SSE。

### 需要运行依赖才能确认的事实

- 真实 LLM 是否返回符合预期的结构化内容。
- 搜索 API 是否成功返回结果。
- PostgreSQL、Redis、Milvus 是否可连接。
- DocMind 和本地知识库是否能完成解析、向量化和召回。
- 一次真实请求是否从后端完整到达浏览器并显示所有图表。

没有 Docker 和外部服务时，可以确认代码结构和构建结果，但不能把静态阅读说成完整端到端运行验证。

## 9. 最小复述练习

请用一两句话补全：

```text
用户在 DeepResearch 页面发送问题后，前端通过 ______ 调用 ______；
后端默认进入 ______，由 ______ 保存 Agent 之间的中间结果，
再按 ______、______、______、______、______、______ 的顺序处理，
最后通过 ______ 返回给前端。
```

参考答案中的关键词依次应包括：`deepsearch/POST /research/stream`、V2、`ResearchState`、六个 Agent、SSE。先自己复述，再对照本课检查。
