# DeepResearch 学习手册：第 8 课

## 从一个问题追踪到最终报告

本课只追踪一件事：用户在 DeepSearch 页面输入一个问题后，系统如何把它变成最终报告。掌握这条链路后，再学习知识库、Text2SQL、记忆和新闻模块会容易很多。

为了便于练习，假设用户输入：

```text
新能源汽车行业未来三年的竞争格局是什么？请给出数据和主要来源。
```

---

## 1. 第一站：React 选择接口

文件：`frontend/src/pages/chat/index.tsx`

在 `sendChat()` 中，代码根据当前聊天类型选择请求。DeepSearch 类型会调用 `api.session.deepsearch()`，而普通聊天走 `/chat/completion`。

对应 API 文件：`frontend/src/api/session.ts` 的 `deepsearch()`。

它发送：

```json
{
  "query": "新能源汽车行业未来三年的竞争格局是什么？请给出数据和主要来源。",
  "session_id": "会话 ID",
  "search_modes": ["web", "local"]
}
```

这里先记住一个工程概念：页面组件不应该直接拼接后端细节。组件调用 API 函数，API 函数统一负责 URL、请求头、流式响应和 Axios 配置。

### 练习 1

打开 `frontend/src/api/session.ts`，回答：

1. DeepSearch 的路径是什么？
2. 为什么 `responseType` 使用 `stream`？
3. 为什么请求头声明 `Accept: text/event-stream`？

---

## 2. 第二站：前端读取 SSE

文件：`frontend/src/pages/chat/index.tsx` 的 `read()` 和 `parseData()`。

核心过程：

```text
fetch/axios 返回 ReadableStream
  → reader.read()
  → TextDecoder 解码
  → 按换行切分
  → 找到 data: 前缀
  → JSON.parse
  → 根据 json.type 更新 React 状态
```

这里不能简单地把每次 `reader.read()` 当成一条完整事件。网络分块可能把一条事件拆成多段，所以代码需要用临时字符串 `temp` 先缓存，再按换行取完整行。

这体现了一个通用工程问题：传输分块边界和业务消息边界不是同一个东西。

### 练习 2

给自己写一个事件示例：

```text
data: {"type":"research_start","query":"..."}

```

说明它经过 `TextDecoder`、换行拆分和 `JSON.parse` 后，最终由哪个分支处理。

---

## 3. 第三站：FastAPI Router 解析请求

文件：`backend/app/router/research_router.py`。

`ResearchRequest` 定义研究请求字段，包括 `query`、`session_id`、`search_modes`、`version` 等。`get_search_web()` 和 `get_search_local()` 把前端的模式数组转换成两个布尔值。

例如：

```text
["web", "local"]
  → search_web=True
  → search_local=True
```

`POST /research/stream` 根据 `version` 选择 V1 或 V2。前端当前使用 V2，因此路由会创建 `DeepResearchV2Service`，再通过 `StreamingResponse` 返回异步事件流。

### 重要判断

Router 的职责是：

- 验证请求数据。
- 选择版本和服务。
- 把服务产生的事件包装成 HTTP 流。

Router 不应该承担六个 Agent 的具体业务逻辑。这样分层后，换前端或写脚本调用同一个接口时，研究流程仍然可以复用。

### 练习 3

如果请求体没有 `query`，会在哪一层首先失败？如果 `query` 有值但 LLM 调用失败，又会在哪一层表现为错误？

答案方向：前者是 Pydantic 请求校验；后者已经进入服务和 Agent 执行阶段。

---

## 4. 第四站：创建或恢复 ResearchState

文件：`backend/app/service/deep_research_v2/graph.py` 和 `state.py`。

`DeepResearchGraph.run()` 先判断是否需要从检查点恢复：

```text
resume=True 且检查点存在
  → 加载旧 state

否则
  → create_initial_state(query, session_id, ...)
  → 用配置覆盖 max_iterations
  → 发送 research_start
```

`ResearchState` 是整个研究过程的共享数据结构。对当前问题，它会逐步经历：

```text
初始：query、session_id、空 outline、空 facts、空 report
规划后：outline、research_questions、key_entities、hypotheses
搜索后：facts、data_points、raw_sources、references
分析后：insights、knowledge_graph、charts、code_executions
写作后：draft_sections、final_report
审核后：critic_feedback、quality_score、pending_search_queries
```

### 为什么不直接在 Agent 之间传字符串

因为每个 Agent 产生的不是一种结果。规划有大纲，搜索有事实和来源，分析有数据和图表，审核有问题列表。如果只传一段字符串，字段语义、恢复、检查点和前端展示都会变得混乱。

### 练习 4

请把下面结果放入正确的状态字段：

- “2024 年销量为 1200 万辆，来源为某行业协会”
- “建议补充欧洲市场数据”
- “按年份比较销量的柱状图”
- “报告第三章”

参考：`facts/data_points`、`pending_search_queries`、`charts`、`draft_sections`。

---

## 5. 第五站：当前真实执行顺序

文件：`backend/app/service/deep_research_v2/graph.py` 的 `run()` 和 `_run_simplified()`。

当前默认执行顺序是：

```text
ChiefArchitect
  → DeepScout
  → DataAnalyst
  → CodeWizard
  → LeadWriter
  → CriticMaster
```

对应阶段事件：

```text
planning
→ researching
→ analyzing
→ writing
→ reviewing
→ completed
```

审核发现问题时，可能进入：

```text
re_researching → rewriting
```

或者：

```text
revising
```

源码证据是：`run()` 中调用 `_run_simplified()`，而 LangGraph 执行分支被注释掉。不要把“定义了图”误认为“默认使用了图”。

---

## 6. 第六站：Agent 如何产生事件

所有 Agent 继承 `BaseAgent`。`_run_simplified()` 用 `asyncio.Queue` 保存 Agent 推送的消息，并在 Agent 运行期间不断把队列消息转成 SSE 事件。

这可以画成：

```text
Agent.process(state)
       │
       ├── 修改 ResearchState
       └── 把阶段消息放入 asyncio.Queue
                         │
                         ▼
              run_agent_with_streaming()
                         │
                         ▼
              FastAPI StreamingResponse
                         │
                         ▼
                  React parseData()
```

因此“状态”和“事件”承担不同任务：

- 状态保存研究结果，供下一个 Agent 使用和检查点恢复。
- 事件告诉前端当前发生了什么，让用户实时看到过程。

状态是长期工作记忆，事件是实时通知通道。

---

## 7. 第七站：六个 Agent 的输入输出

| Agent | 主要输入 | 主要输出 |
|---|---|---|
| `ChiefArchitect` | query、搜索模式 | outline、research_questions、key_entities、hypotheses |
| `DeepScout` | outline、研究问题、搜索开关 | facts、data_points、raw_sources、references |
| `DataAnalyst` | facts、data_points | insights、knowledge_graph、结构化分析 |
| `CodeWizard` | 数据点、需要图表的章节 | charts、code_executions、代码结果 |
| `LeadWriter` | outline、facts、分析结果、charts | draft_sections、final_report、references |
| `CriticMaster` | final_report、outline、证据 | critic_feedback、quality_score、补搜查询或修订方向 |

注意：这些是职责边界，不代表每个 Agent 只读一两个字段。真正追踪时应进入对应 `process()` 查看 prompt、工具调用和状态写回。

---

## 8. 第八站：前端如何把事件变成界面

前端 `parseData()` 收到事件后，不是简单把所有文本拼到一个框里，而是按类型放到不同的数据结构：

```text
researchSteps
researchDetailsRef
selectedResearchDetail
currentChatItem
researchDataVersion
```

例如：

- `research_step` 创建或更新左侧阶段卡片。
- `search_results` 放入搜索详情。
- `knowledge_graph` 放入分析详情。
- 图表事件放入 charts。
- `research_complete` 将最终报告放入写作详情，并更新引用。

之后 `ResearchDetail` 再把这些数据传给搜索结果、知识图谱、图表和报告组件。

报告渲染文件：

```text
frontend/src/pages/chat/component/research-detail/process-report.tsx
```

它会把 Markdown、图表和知识图谱组合成内容块，因此最终页面不是单一纯文本。

---

## 9. 第九站：检查点怎样连接后端和前端

后端每个主要阶段结束后调用 `save_checkpoint_async()`。保存内容包括：

```text
state_json       完整后端 ResearchState
ui_state_json    前端恢复需要的研究步骤和展示数据
phase            当前阶段
iteration        当前审核轮次
status           running/completed/failed 等
final_report     最终报告
```

前端切换或刷新会请求检查点接口，把 `ui_state_json` 重新变成步骤和详情。

这是一种常见的“业务状态与视图状态分离”设计：后端状态适合继续计算，UI 状态适合快速恢复页面。

---

## 10. 用日志验证你的理解

不用修改业务代码，也可以用以下方式验证：

1. 浏览器 Network 查看 `/research/stream`。
2. 后端日志搜索 `Starting agent` 和 `[SSE YIELD]`。
3. 检查研究事件的 `type` 和 `phase`。
4. 请求 `/research/checkpoint/{session_id}` 查看阶段和状态。
5. 对照页面右侧研究详情是否产生搜索结果、图表和报告。

如果后端日志显示 Agent 已完成、浏览器却没有内容，重点检查 SSE 事件格式和前端 `parseData()`；如果页面收到 `research_step` 但详情为空，重点检查 `researchDetailsRef` 的 key 是否和 `stepType` 一致。

---

## 11. 本课必须掌握的五句话

1. 页面通过 `/research/stream` 发起 DeepResearch，返回的是 SSE 流。
2. Router 负责校验和分流，Graph 负责编排，Agent 负责具体研究职责。
3. `ResearchState` 是 Agent 之间共享的结构化工作记忆。
4. 当前默认执行路径是 `_run_simplified()`，它用队列支持实时 SSE。
5. 检查点保存后端研究状态和前端 UI 状态，用于恢复和继续工作。

---

## 12. 作业

请你画一张自己的图，必须包含以下节点：

```text
Chat 页面
deepsearch API
/research/stream
ResearchRequest
DeepResearchV2Service
DeepResearchGraph.run
ResearchState
六个 Agent
asyncio.Queue
SSE
parseData
ResearchDetail
checkpoint
```

然后回答：

1. 如果 `research_start` 能看到，但 `research_step` 看不到，故障可能在哪些位置？
2. 如果报告能显示，但图表没有，应该沿哪条数据路径排查？
3. 如果刷新后报告恢复但研究步骤不恢复，应该检查哪个 JSON 字段？

