# DeepResearch 学习手册·第 61 课

## 综合数据流验收：从输入到报告

这一课不是新增模块，而是把已经读过的代码连成一条你能够独立讲清楚的完整链路。

---

## 1. 用户输入如何进入系统

前端 DeepResearch 请求在：

```text
frontend/src/pages/chat/index.tsx
  → frontend/src/api/session.ts::deepsearch()
```

请求的核心结构是：

```json
{
  "query": "新能源汽车行业竞争格局",
  "session_id": "会话 ID",
  "search_modes": ["web", "local"]
}
```

`deepsearch()` 同时设置：

- `Accept: text/event-stream`
- `responseType: stream`
- `adapter: fetch`

这三个设置告诉浏览器：响应不是一次性 JSON，而是一个需要持续读取的流。

---

## 2. Router 如何选择主链路

后端入口：

```text
backend/app/router/research_router.py::stream_research()
```

Router 根据请求中的 `version` 选择实现：

```text
POST /research/stream + version=v2
  → DeepResearchV2Service.research()

其他 V1 路径
  → 原有 ResearchService.research_stream()
```

V2 还会从 `search_modes` 推导：

- 是否启用网络搜索 `search_web`。
- 是否启用本地知识库搜索 `search_local`。

这说明同一个查询的研究范围由请求参数参与控制，而不是完全由 Agent 自己决定。

---

## 3. V2 Service 如何把请求交给图执行器

文件：`backend/app/service/deep_research_v2/service.py`。

`DeepResearchV2Service.research()` 会：

1. 没有 `session_id` 时生成 UUID。
2. 记录开始研究或恢复研究的日志。
3. 调用 `self.graph.run()`。
4. 对每个事件调用 `_format_sse()`。
5. 最后发送 `data: [DONE]\n\n`。

事件格式类似：

```text
data: {"type":"research_step","content":{...}}

```

因此，Agent 产生的 Python 字典不是直接发给浏览器，中间还要经过 JSON 序列化和 SSE 包装。

---

## 4. ResearchState 是什么

文件：`backend/app/service/deep_research_v2/state.py`。

它是所有 Agent 共享的工作台，主要字段可以按功能分组：

| 分组 | 典型字段 | 用途 |
|---|---|---|
| 输入 | `query`、`session_id` | 保存本次研究身份 |
| 控制 | `phase`、`iteration`、`max_iterations` | 控制流程阶段和审核轮数 |
| 规划 | `outline`、`research_questions`、`hypotheses` | 保存 ChiefArchitect 的计划 |
| 证据 | `facts`、`data_points`、`raw_sources` | 保存搜索和结构化数据 |
| 分析 | `charts`、`code_executions`、`insights` | 保存分析结果和代码执行记录 |
| 写作 | `draft_sections`、`final_report`、`references` | 保存报告草稿和最终报告 |
| 审核 | `critic_feedback`、`unresolved_issues`、`quality_score` | 保存质量检查结果 |
| 流式 | `logs`、`errors`、`messages` | 保存日志、错误和 Agent 消息 |

Agent 之间不是靠互相直接调用完成协作，而是通过读取和更新这些共享字段交接结果。

---

## 5. 六个 Agent 的数据交接

默认简化流程可以复述为：

```text
ChiefArchitect
  写 outline、research_questions、key_entities、hypotheses
        ↓
DeepScout
  读取 outline 和搜索开关，写 facts、raw_sources、data_points
        ↓
DataAnalyst
  读取 facts/data_points，写 insights、knowledge_graph、charts
        ↓
CodeWizard
  读取数据分析任务，生成并执行 Python，补充 code_executions/charts
        ↓
LeadWriter
  读取大纲、事实、洞察、图表和来源，写 draft_sections/final_report
        ↓
CriticMaster
  读取报告和证据，写 critic_feedback、quality_score、pending_search_queries
```

审核结果可能产生两种后续：

- 信息不足：补充搜索，再重新写作。
- 质量可接受：完成研究。

这里要注意：这是当前手写的简化执行顺序；不能把代码中存在的 LangGraph 节点设计直接当成默认运行路径。

---

## 6. 同一份结果如何到达页面

后端事件通过 SSE 到达 `frontend/src/pages/chat/index.tsx`，前端先读取 `ReadableStream`，再把字节拼入缓冲区，按空行切分事件并解析 JSON。

典型映射是：

```text
research_step
  → researchSteps
  → 研究过程组件

search_results
  → detail.searchResults
  → 来源/搜索结果面板

knowledge_graph
  → detail.knowledgeGraph
  → 知识图谱组件

charts / chart
  → detail.charts
  → Visualization / ECharts

research_complete
  → detail.streamingReport
  → ProcessReport
```

由于部分数据存放在 `researchDetailsRef` 中，页面还需要通过 `researchDataVersion` 触发 React 重新渲染。数据已经存在但页面没有变化时，应检查“状态写入”和“重新渲染触发”两个环节。

---

## 7. 数据库和 Redis 在这条链路中的位置

PostgreSQL 主要保存持久化业务数据，例如：

- 用户、会话和消息。
- `ResearchCheckpoint`。
- 知识库、文档和长期记忆元数据。

检查点中的：

- `state_json`：后端研究状态。
- `ui_state_json`：前端步骤、搜索结果、图表、图谱和报告恢复数据。
- `final_report`：最终报告文本。

Redis 在取消流程中保存：

```text
research:cancel:{session_id}
```

Graph 在阶段边界检查这个标志，并发出 `research_cancelled`。Redis 取消标志不是研究状态本身，也不替代 PostgreSQL 检查点。

---

## 8. 综合故障判断

遇到下面的现象，可以这样判断：

### 情况 A：请求没有进入后端

检查前端 Network、按钮事件、登录状态和 Axios 请求头。

### 情况 B：后端返回 200，但没有任何研究步骤

检查 SSE 响应头、Service 生成器和 Graph 是否创建初始状态。

### 情况 C：有研究步骤，但没有搜索结果

检查 DeepScout、`search_web/search_local`、搜索 API、Embedding/Milvus 和外部 Key。

### 情况 D：有 facts，但没有 charts

检查 DataAnalyst 和 CodeWizard 的输出、图表事件以及 `state["charts"]`，不要先假设是 ECharts 组件问题。

### 情况 E：实时页面有报告，刷新后没有报告

检查检查点是否保存、`ui_state_json` 是否包含报告，以及前端恢复映射。

---

## 9. 这条链路的面试表达模板

可以用下面的顺序回答“请介绍一次研究请求”：

```text
用户在 React 聊天页输入问题后，前端通过 deepsearch() 以 Fetch 流方式请求 POST /research/stream，并携带 query、session_id 和 search_modes。FastAPI Router 根据 version 选择 V2，调用 DeepResearchV2Service。V2 创建或恢复研究状态，再由 DeepResearchGraph 当前默认的 _run_simplified() 按六个 Agent 顺序执行。Agent 通过 ResearchState 交接 outline、facts、data_points、charts、final_report 和 critic_feedback。事件经过 asyncio.Queue 和 SSE 返回浏览器，前端按事件类型更新研究步骤、搜索结果、图谱、图表和报告。阶段状态写入检查点，Redis 负责协作式取消。实际运行还依赖 PostgreSQL、Redis、Milvus、外部搜索和 LLM 配置。
```

这个回答同时覆盖了入口、执行、状态、流式输出、持久化和依赖边界。

---

## 综合验收题

请用自己的话回答下面一个场景：

> 页面已经显示 `research_step` 和 `search_results`，但最终没有 `research_complete`；后端日志显示 CodeWizard 执行代码失败。请说明：结果已经证明哪些阶段成功？下一步查看哪些状态字段、事件和文件？为什么不能只修改前端报告组件？

回答时至少提到：`ResearchState`、`code_executions`、`charts`、Agent 错误事件、CodeWizard 的代码生成/执行链，以及 LeadWriter 尚未拿到完整输入这一事实。

