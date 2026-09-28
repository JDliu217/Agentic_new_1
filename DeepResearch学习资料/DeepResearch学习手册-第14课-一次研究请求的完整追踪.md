# DeepResearch 学习手册·第 14 课

## 一次研究请求的完整追踪

本课只追踪一件事：用户在前端提交一个深度研究问题后，系统如何从浏览器一路走到最终报告，再把过程和结果显示回来。

源码根目录：`D:\课\s4-6\industry_information_assistant`

---

## 1. 先看总数据流

```text
用户输入问题
  ↓
frontend/src/api/session.ts: deepsearch()
  ↓ POST /research/stream
backend/app/router/research_router.py: stream_research()
  ↓ version == "v2"
DeepResearchV2Service.research()
  ↓
DeepResearchGraph.run()
  ↓ 当前默认真实路径
_run_simplified()
  ↓
ChiefArchitect → DeepScout → DataAnalyst → CodeWizard
  ↓
LeadWriter → CriticMaster
  ↓ 审核需要时循环：补充搜索或修订
research_complete 事件
  ↓ SSE
frontend/src/pages/chat/index.tsx: read() / parseData()
  ↓
研究步骤、搜索结果、图表、报告、引用
```

关键结论：当前默认执行并不是“前端直接调用六个 Agent”，而是所有 Agent 共享一个 `ResearchState`，由后端图服务按阶段驱动。

---

## 2. 浏览器发出了什么

`frontend/src/api/session.ts` 的 `deepsearch()` 调用：

```ts
request.post('/research/stream', params, {
  headers: { Accept: 'text/event-stream' },
  responseType: 'stream',
  adapter: 'fetch'
})
```

请求体至少包含：

```json
{
  "query": "用户的问题",
  "session_id": "可选会话 ID",
  "search_modes": ["web", "local"]
}
```

前端这里使用的是浏览器的 `ReadableStream`。它不是一次性等待完整 JSON，而是不断读取后端发来的字节块。

### 2.1 为什么使用流式输出

深度研究可能需要多次模型调用、搜索和代码执行。如果等全部完成，用户会长时间看不到反馈。SSE 让前端先看到：

- 研究开始
- 当前阶段
- 大纲
- 搜索结果
- 图表
- 报告生成
- 审核和补充搜索
- 最终完成

流式输出解决的是交互等待问题，不会自动提高研究结论的正确性。

---

## 3. FastAPI 路由如何分流

`backend/app/router/research_router.py` 的 `ResearchRequest` 定义了：

- `query`
- `session_id`
- `max_iterations`
- `kb_name`
- `search_web`
- `search_local`
- `search_modes`
- `version`

`version` 默认值是 `v2`。路由先把 `search_modes` 转换成两个布尔值：

```text
search_modes 中有 web   → search_web = true
search_modes 中有 local → search_local = true
```

随后：

```python
service_v2 = get_research_service_v2()
async for event in service_v2.research(...):
    yield event
```

返回类型是 `StreamingResponse`，媒体类型为 `text/event-stream`。

### 3.1 V1 和 V2 在这里分开

当 `version == "v2"`：

```text
DeepResearchV2Service
→ 多 Agent 状态流
```

否则走旧的 `ResearchService.research_stream()`：

```text
ResearchService
→ ReActController
→ ToolExecutor
→ 搜索、知识库、Text2SQL 等工具
```

这是理解项目演进的第一个分叉点。

---

## 4. Service 层做了什么

`DeepResearchV2Service.research()` 负责三件事：

1. 没有 `session_id` 时生成 UUID。
2. 调用 `self.graph.run(...)`。
3. 把每个事件格式化成 SSE：

```text
data: {"type": "事件类型", ...}\n\n
```

研究流程抛出异常时，Service 会发送 `type = error` 的事件；流程结束时发送：

```text
data: [DONE]\n\n
```

`[DONE]` 只是传输结束标记，不等同于业务上的 `research_complete`。前者告诉前端“流结束了”，后者包含最终报告和引用。

---

## 5. 初始状态：所有 Agent 的共享工作记忆

`state.py` 的 `ResearchState` 是整个 V2 的核心契约。它包含：

```text
query / session_id / phase / iteration / max_iterations
search_web / search_local
outline / research_questions / hypotheses / knowledge_graph
facts / data_points / raw_sources
charts / code_executions / insights
draft_sections / final_report / references
critic_feedback / unresolved_issues / quality_score
pending_search_queries
logs / errors / messages
```

这不是一个只保存最终答案的对象，而是整个研究过程的工作记忆：

- ChiefArchitect 写 `outline` 和研究问题。
- DeepScout 写 `facts`、`raw_sources`、`references`。
- DataAnalyst 写 `data_points`、`insights` 和分析相关状态。
- CodeWizard 写 `charts`、`code_executions`。
- LeadWriter 写 `draft_sections` 和 `final_report`。
- CriticMaster 写 `critic_feedback`、`quality_score` 和下一步路由信息。

因此，Agent 协作的关键不是 Agent 之间直接互相调用，而是围绕共享状态读写。

---

## 6. 为什么说 LangGraph 是设计层

`DeepResearchGraph.__init__()` 在 LangGraph 可用时会构建：

```text
plan → research → analyze → write → review
                                      ↓
                          revise 或 complete
```

但是 `run()` 中的 LangGraph 执行代码被注释掉了，当前直接执行：

```python
async for event in self._run_simplified(state):
    yield event
```

原因写在源码注释中：手写版本可以使用 `asyncio.Queue` 实时发送 SSE，LangGraph 版本当时不能满足相同的实时输出方式。

所以学习时必须区分：

| 概念 | 含义 |
| --- | --- |
| LangGraph 图 | 设计好的状态机和条件边 |
| `_run_simplified()` | 当前默认真正执行的流程 |
| `run_sync()` | 不走 SSE 的同步执行路径 |

---

## 7. `_run_simplified()` 如何实时传消息

简化执行路径先创建：

```python
message_queue = asyncio.Queue()
state["_message_queue"] = message_queue
```

每个 Agent 继承 `BaseAgent`。当 Agent 调用：

```python
self.add_message(state, "事件类型", content)
```

基类会：

1. 把消息追加到 `state["messages"]`。
2. 如果存在 `_message_queue`，立即 `put_nowait()`。

图执行器通过 `run_agent_with_streaming()` 启动 Agent 任务，同时不断从队列取消息并 `yield`。这就形成：

```text
Agent 产生事件
→ asyncio.Queue
→ Graph yield
→ Service 格式化 SSE
→ 浏览器读取
```

Agent 任务结束后，执行器还会清空队列中剩余的事件，避免最后几条消息丢失。

---

## 8. 六个阶段的真实顺序

### 8.1 规划

```text
phase = planning
ChiefArchitect.process(state)
```

Architect 调用 LLM 生成大纲、研究问题和章节属性，并发送 `outline`、`research_step` 等事件。

### 8.2 搜索

```text
phase = researching
DeepScout.process(state)
```

Scout 依据大纲执行网络搜索和可选的本地知识库搜索，将结果整理成事实、来源和引用，发送 `search_results` 事件。

### 8.3 分析

```text
phase = analyzing
DataAnalyst.process(state)
CodeWizard.process(state)
```

DataAnalyst 先识别需要分析的数据和洞察；CodeWizard 再生成并执行 Python，保存图表和执行记录。当前手写流程中这两个 Agent 是连续执行的。

### 8.4 写作

```text
phase = writing
LeadWriter.process(state)
```

Writer 遍历大纲，结合事实、数据、图表和引用生成章节草稿及最终报告。

### 8.5 审核

```text
phase = reviewing
CriticMaster.process(state)
```

Critic 检查来源、逻辑、偏差、幻觉、时效性和完整性等问题，并更新 `critic_feedback`、`unresolved_issues` 与 `phase`。

### 8.6 补充搜索或修订

审核后可能出现三种路线：

```text
COMPLETED       → 结束
RE_RESEARCHING  → Scout 补充搜索 → Writer 重新写作
REVISING        → Writer 只修订文字
```

循环受 `state["max_iterations"]` 限制。

---

## 9. 检查点和前端恢复

每个主要阶段结束后，`save_checkpoint_async()` 会：

1. 从后端状态整理 UI 状态。
2. 记录研究步骤和统计值。
3. 调用检查点服务保存状态。
4. 发送 `checkpoint_saved` 事件。

UI 状态包含：

```text
research_steps
search_results
charts
knowledge_graph
streaming_report
references
```

这解释了为什么项目既保存后端 `ResearchState`，又保存面向前端的 UI 状态：后端状态适合继续执行，UI 状态适合页面恢复。

如果用户刷新页面，恢复逻辑需要重新建立：

- 研究步骤列表
- 每个步骤的详情对象
- 搜索结果和图表
- 当前报告

---

## 10. 前端如何解释事件

`frontend/src/pages/chat/index.tsx` 中的 `read()`：

1. 从 `ReadableStream.getReader()` 读取字节。
2. 用 `TextDecoder` 转为文本。
3. 使用换行符拆分 SSE 行。
4. 找到 `data: ` 前缀后交给 `parseData()`。

`parseData()` 根据 `json.type` 分流：

| 事件 | 前端动作 |
| --- | --- |
| `research_start` | 清空旧研究详情，建立新研究上下文 |
| `research_step` | 创建或更新规划、搜索、分析、写作步骤 |
| `search_results` | 更新搜索结果数量和列表 |
| `knowledge_graph` | 写入知识图谱 |
| `charts` | 写入分析步骤和报告图表 |
| `phase` | 更新阶段文字和时间线 |
| `outline` | 添加研究大纲到过程记录 |
| `research_complete` | 设置最终报告、引用并把步骤标记完成 |
| `research_cancelled` | 结束为取消状态 |
| `error` | 显示错误 |

前端使用 `researchDetailsRef` 保存每种步骤的详情，并用 `researchDataVersion` 强制触发聚合数据更新。这是为了处理事件到达频繁、对象需要增量更新的场景。

---

## 11. 一次请求中的三个“状态”不要混淆

### 11.1 后端工作状态

`ResearchState`：Agent 读写的事实、数据、大纲、报告和审核状态。

### 11.2 传输事件状态

SSE 事件：告诉浏览器刚刚发生了什么，例如 `phase`、`search_results`、`charts`。

### 11.3 持久化恢复状态

检查点：用于中断恢复和刷新页面后重建 UI。

三者关系是：

```text
ResearchState
→ 产生事件
→ 事件驱动前端实时显示
→ 阶段结束时把状态整理成 checkpoint
```

事件不一定包含完整状态；检查点也不等于每条事件的原样存档。

---

## 12. 追踪故障时的顺序

当页面没有最终报告时，按下面顺序排查：

1. 浏览器 Network 是否请求了 `/research/stream`？
2. 请求体中的 `version` 是否为 `v2`？
3. FastAPI 是否进入 `stream_research()` 的 V2 分支？
4. 是否出现 `research_start`？
5. 是否收到 `phase: planning`？
6. Architect 是否把大纲写进 `state["outline"]`？
7. Scout 是否产生 `facts` 或 `search_results`？
8. DataAnalyst/CodeWizard 是否产生图表或错误？
9. Writer 是否写入 `state["final_report"]`？
10. Critic 是否把流程置为 `COMPLETED` 或进入循环？
11. 后端是否发出 `research_complete`？
12. 前端 `parseData()` 是否解析到了该事件？

不要一开始就猜“模型回答错了”。先确定请求、状态、事件和渲染分别在哪一层断开。

---

## 13. 当前实现的几个真实注意点

- `ResearchRequest.max_iterations` 默认写成 3，但 V2 的 POST 路径把它交给 V2 服务时没有显式传入；V2 实际使用配置中的 `max_iterations`。
- `DeepResearchV2Service.research()` 接收 `kb_name`，但传给 `graph.run()` 的调用中没有把 `kb_name` 继续传下去；本地知识库搜索还存在集合命名问题，见第 13 课。
- `run()` 的 LangGraph 执行分支被注释，不能把“已构建图”说成“当前请求一定通过 LangGraph 执行”。
- `run_sync()` 和 `_run_simplified()` 的事件行为不同；调试页面实时显示时应优先看流式路径。
- 前端按换行拆分 SSE，真实网络分片可能把一行拆成多块；代码通过 `temp` 缓冲部分数据，但排错时仍应查看原始 Network 响应。

---

## 14. 练习：你来追踪

假设用户提交：

```text
“分析中国储能行业 2024 年市场规模、主要企业和未来趋势，并给出数据来源。”
```

请回答：

1. 前端调用哪个函数和 URL？
2. 后端如何判断走 V1 还是 V2？
3. 初始状态中至少有哪五个字段会在后续被填充？
4. 哪个 Agent 负责生成大纲？哪个 Agent 负责搜索？
5. 哪个 Agent 生成 Python 图表？图表最终写到哪里？
6. 审核发现缺少企业数据时，可能走哪条路线？
7. 前端收到 `research_complete` 后，至少更新哪两类内容？
8. 如果 `research_complete` 已在 Network 中出现但页面没有报告，你先查后端还是前端？为什么？

### 我的回答

<!-- 在这里写你的答案；下一次教学会逐题批改 -->


### 我画的数据流

<!-- 在这里画箭头或贴你的 Mermaid 草图 -->


### 我仍然混淆的三个概念

<!-- 在这里记录问题 -->

