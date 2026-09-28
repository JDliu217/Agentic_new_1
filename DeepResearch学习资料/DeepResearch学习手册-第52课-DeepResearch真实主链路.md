# DeepResearch 学习手册·第 52 课

## 一次 DeepResearch 请求的真实执行主链

本课是项目主干课。目标是让你能回答：

- 请求从哪个接口进入？
- V2 服务怎样创建状态？
- 六个 Agent 按什么顺序工作？
- Agent 如何把中间结果交给前端？
- LangGraph 代码和当前真实执行有什么区别？

---

## 1. 请求从前端进入

前端调用 frontend/src/api/session.ts 的 deepsearch 函数，向 POST /research/stream 发送：

~~~~json
{
  "query": "用户的问题",
  "session_id": "可选会话 ID",
  "search_modes": ["web", "local"]
}
~~~~

frontend/src/pages/chat/index.tsx 根据聊天类型选择 deepsearch，并读取返回的 ReadableStream。

后端入口是 backend/app/router/research_router.py 的 stream_research。

请求模型 ResearchRequest 负责把 search_modes 转换成两个布尔值：

- search_web：是否启用网络搜索
- search_local：是否启用本地知识库

当 version 为 v2 时，路由创建 DeepResearchV2Service，并调用 service_v2.research。

---

## 2. V2 服务做什么

DeepResearchV2Service 位于 backend/app/service/deep_research_v2/service.py。

它主要负责三件事：

1. 读取配置并创建 DeepResearchGraph。
2. 接收 query、session_id、搜索开关和恢复参数。
3. 把 Graph 产生的事件格式化成 SSE。

格式化后的每个事件形如：

~~~~text
data: {"type":"research_step","content":{...}}

~~~~

研究结束后，Service 还发送：

~~~~text
data: [DONE]

~~~~

Service 本身不是六个 Agent 的执行者；真正的阶段调度在 DeepResearchGraph。

---

## 3. ResearchState 是共享工作台

ResearchState 位于 backend/app/service/deep_research_v2/state.py，是 TypedDict。

可以把它理解成一张所有 Agent 共用的工作表。

### 基础字段

- query
- session_id
- phase
- iteration
- max_iterations
- search_web
- search_local

### 规划字段

- outline
- mind_map
- key_entities
- research_questions
- hypotheses
- knowledge_graph

### 证据字段

- facts
- data_points
- raw_sources

### 分析字段

- charts
- code_executions
- insights

### 报告字段

- draft_sections
- final_report
- references

### 质量字段

- critic_feedback
- unresolved_issues
- quality_score
- pending_search_queries

### 工程字段

- logs
- errors
- messages

一个 Agent 的输出不是单独返回给下一个 Agent 的参数，而是写入这张共享工作台，后续 Agent 再从同一个 state 读取。

---

## 4. 当前默认执行顺序

当前真实默认路径来自 graph.py 的 _run_simplified：

~~~~text
1. ChiefArchitect
2. DeepScout
3. DataAnalyst
4. CodeWizard
5. LeadWriter
6. CriticMaster
7. 根据审核结果，可能回到 DeepScout 或 LeadWriter
8. research_complete
~~~~

对应阶段：

| Agent | 主要职责 | 主要写入 |
|---|---|---|
| ChiefArchitect | 理解问题、生成大纲和研究问题 | outline、research_questions、hypotheses |
| DeepScout | 网络/本地搜索、提取证据 | facts、raw_sources、references、data_points |
| DataAnalyst | 提取结构化数据、知识图谱和 ECharts 配置 | data_points、knowledge_graph、charts |
| CodeWizard | 运行计算和图表代码，补充分析结果 | code_executions、charts、insights |
| LeadWriter | 生成章节草稿和最终报告 | draft_sections、final_report |
| CriticMaster | 检查来源、逻辑、遗漏和幻觉 | critic_feedback、unresolved_issues、quality_score |

---

## 5. 为什么 DataAnalyst 和 CodeWizard 都在分析阶段

两者不是完全重复：

### DataAnalyst

更关注从事实和证据中提取结构化信息：

- 识别时间序列和分布数据。
- 生成知识图谱。
- 准备 ECharts 配置。
- 发送 charts 和 knowledge_graph 事件。

### CodeWizard

更关注需要计算或执行代码的任务：

- 根据分析需求生成 Python。
- 在受限环境中执行。
- 计算统计结果。
- 生成图片或图表补充结果。
- 记录执行错误和修复尝试。

当前手写流程会先执行 DataAnalyst，再执行 CodeWizard。二者都在同一个 ResearchState 上工作，因此 CodeWizard 可以读取 DataAnalyst 已经写入的数据。

---

## 6. asyncio.Queue 如何把 Agent 消息变成 SSE

每次执行 _run_simplified，Graph 创建一个 asyncio.Queue，并把它放入 state 的内部字段。

BaseAgent.add_message 会把 Agent 产生的事件放入队列，例如：

- research_step
- search_results
- knowledge_graph
- charts
- agent_message
- error

Graph 同时创建一个 Agent task：

~~~~python
task = asyncio.create_task(agent.process(state))
~~~~

然后循环读取队列：

~~~~python
msg = await asyncio.wait_for(message_queue.get(), timeout=0.5)
yield msg
~~~~

这形成了两条并行关系：

~~~~text
Agent.process(state)
      └── add_message → asyncio.Queue

Graph 读取 Queue
      └── yield event → Service 格式化为 SSE
                              └── 浏览器 ReadableStream
~~~~

Queue 只服务于当前请求的实时事件，不是数据库，也不是跨请求消息总线。研究结束后 Graph 会清理它。

---

## 7. 阶段切换和检查点

Graph 在每个主要阶段前后做几件事：

1. 检查 Redis 中是否有取消标志。
2. 设置 state.phase。
3. 发送 phase 事件。
4. 执行 Agent。
5. 清空 state.messages，避免旧消息重复。
6. 更新 UI 状态。
7. 保存检查点。

主要阶段事件包括：

~~~~text
planning
researching
analyzing
writing
reviewing
re_researching
rewriting
revising
~~~~

检查点同时保存后端研究状态和前端 UI 状态。前者用于继续处理研究数据，后者用于恢复页面上的步骤、来源、图表、知识图谱和报告展示。

---

## 8. CriticMaster 如何决定后续路径

审核阶段结束后，代码会根据 state.phase 和 iteration 决定：

### 发现需要补充证据

~~~~text
reviewing
  → re_researching
  → DeepScout 补充搜索
  → rewriting
  → LeadWriter 重新写作
~~~~

### 只需要文字修订

~~~~text
reviewing
  → revising
  → LeadWriter 修订
~~~~

### 没有需要继续处理的问题

~~~~text
reviewing
  → completed
  → research_complete
~~~~

max_iterations 用于限制审核和修订循环，防止任务无限运行。

---

## 9. 最终事件如何形成

流程结束时，Graph：

1. 把 phase 设置为 completed。
2. 更新检查点状态。
3. 把内部 references 和 facts 转成前端可展示的 references。
4. 发送 research_complete。
5. Service 再发送 [DONE]。

research_complete 主要包含：

- final_report
- quality_score
- facts_count
- charts_count
- iterations
- references

前端收到后，把 final_report 放到聊天内容，把 references 转成来源，把研究步骤标记为完成。

---

## 10. LangGraph 为什么不是当前主链

graph.py 同时包含：

- _build_langgraph
- _run_with_langgraph
- _run_simplified

但 run 方法当前明确执行：

~~~~python
async for event in self._run_simplified(state):
    yield event
~~~~

原因在源码注释中已经说明：LangGraph 分支会批量处理消息，不能满足当前需要的实时 SSE 输出。

所以学习项目时要区分：

- 设计中的 LangGraph 图：有节点和条件边。
- 当前默认运行实现：手写阶段顺序加 asyncio.Queue。

不能因为看到 StateGraph 就断言运行时一定走 LangGraph。

---

## 11. 一次请求的完整追踪图

~~~~text
React deepsearch
  ↓
POST /research/stream
  ↓
ResearchRequest
  ↓
DeepResearchV2Service.research
  ↓
DeepResearchGraph.run
  ↓
create_initial_state
  ↓
_run_simplified
  ↓
ChiefArchitect → DeepScout → DataAnalyst
  ↓
CodeWizard → LeadWriter → CriticMaster
  ↓
Queue 中的事件持续 yield
  ↓
Service 转为 data: JSON
  ↓
React 缓冲并 parseData
  ↓
研究步骤、搜索结果、图表、图谱、报告
~~~~

---

## 12. 源码确认和真实验证的区别

源码可以确认：

- 当前默认版本是 V2。
- 当前默认执行 _run_simplified。
- Agent 顺序和状态字段。
- 事件格式和检查点调用位置。

仍需要真实环境才能确认：

- 外部 LLM 是否返回符合预期的 JSON。
- Bocha 搜索是否真实返回结果。
- DocMind、Milvus 和本地知识库是否联通。
- 取消、恢复和检查点是否在真实 Redis/PostgreSQL 环境中正常工作。
- 前端每种事件是否都能正常显示。

---

## 13. 小练习

当前默认的 V2 研究流程中，哪个对象负责让 Agent 的中间事件实时传到前端？

A. PostgreSQL 的 ResearchCheckpoint

B. asyncio.Queue 加上 Graph 的事件 yield，再由 Service 格式化成 SSE

C. Milvus collection

D. React 的定时器

建议回答选项字母，并说明为什么 ResearchState 和 asyncio.Queue 不是同一个东西。

---

## 留白：我的主链路复述

请求入口：

默认版本：

真实执行器：

共享状态：

实时事件通道：

六个 Agent 的顺序：

审核后可能的两条分支：

最终事件：

---

## 源码定位

- backend/app/router/research_router.py：POST /research/stream 和版本选择
- backend/app/service/deep_research_v2/service.py：服务入口和 SSE 格式化
- backend/app/service/deep_research_v2/graph.py：状态初始化、Agent 顺序、Queue、检查点和完成事件
- backend/app/service/deep_research_v2/state.py：ResearchState 和阶段枚举
- backend/app/service/deep_research_v2/agents/base.py：Agent 消息入队
- frontend/src/api/session.ts：deepsearch 请求
- frontend/src/pages/chat/index.tsx：SSE 缓冲和事件分发

