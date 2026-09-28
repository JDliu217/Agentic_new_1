# DeepResearch 学习手册·第 24 课

## 一次请求的状态演化与前端实时渲染

本课把后端共享状态、六个 Agent、SSE 事件和 React 研究面板放在同一条链路里。学完后，你应该能回答：

> 用户提交一个研究问题以后，后端每个阶段修改了什么，前端又如何把这些修改显示出来？

源码依据：

- `D:\课\s4-6\industry_information_assistant\backend\app\service\deep_research_v2\state.py`
- `D:\课\s4-6\industry_information_assistant\backend\app\service\deep_research_v2\graph.py`
- `D:\课\s4-6\industry_information_assistant\frontend\src\pages\chat\index.tsx`

---

## 1. 上一轮四个问题的标准答案

### 1.1 为什么使用 SSE，而不是一次返回完整 JSON？

研究请求不是一个很快结束的数据库查询。它需要经过规划、搜索、分析、代码执行、写作和审核，耗时主要来自外部搜索和多次 LLM 调用。

如果后端等所有阶段结束后才返回一个 JSON，浏览器在这段时间只能显示一个笼统的加载状态。项目使用 `text/event-stream`，把阶段变化、搜索结果、图表、审核信息和最终报告分别推送给前端，因此用户能看到过程，也能在中途取消研究。

这里的 SSE 是“服务器向浏览器持续发送文本事件”的传输方式，不是 Agent 本身，也不是 LangGraph。前端在 `index.tsx` 中读取 `ReadableStream`，按 `data: {...}` 解析事件，再根据 `json.type` 更新页面。

### 1.2 `ResearchState` 在多个 Agent 之间起什么作用？

`ResearchState` 是结构化的共享工作台。Architect 写入大纲，Scout 读取大纲并写入事实，DataAnalyst 读取事实并写入数据点和图谱，Writer 读取这些材料生成报告，Critic 再读取报告和证据进行审核。

它还保存流程控制字段，例如 `phase`、`iteration` 和 `max_iterations`，以及前端需要的图表、引用和消息。它不是数据库表，也不是一段把所有内容拼在一起的聊天字符串；它是本次研究运行期间的内存状态，检查点服务才负责把状态持久化下来。

### 1.3 `researchSteps` 和 `researchDetailsRef` 分别保存什么？

在 `frontend/src/pages/chat/index.tsx` 中：

```text
researchSteps
    页面左侧或顶部展示的步骤列表
    例如 planning、researching、analyzing、writing、reviewing
    保存标题、状态和统计数字

researchDetailsRef
    一个 Map<stepType, ResearchDetailData>
    保存某一步的详细数据
    例如搜索结果、图表、知识图谱和流式报告
```

`researchSteps` 是 React state，更新后会触发渲染。`researchDetailsRef` 是 `useRef`，直接修改 Map 不会自动触发渲染，所以收到搜索结果、知识图谱或图表后，代码会调用 `setSelectedResearchDetail`，并递增 `researchDataVersion`，让依赖这些详情的聚合结果重新计算。

不要把 `researchDetailsRef` 理解成后端缓存。它只是当前浏览器页面保存研究详情的可变引用；切换会话或收到新的 `research_start` 时会清空。

### 1.4 为什么不能只说“项目使用 LangGraph”？

项目确实在 `graph.py` 中定义了 LangGraph 图，节点包括 `plan`、`research`、`analyze`、`write`、`review` 和 `revise`。但 `DeepResearchGraph.run()` 当前把 LangGraph 的执行代码注释掉，始终调用 `_run_simplified()`，因为后者使用 `asyncio.Queue`，可以把 Agent 产生的消息实时转成 SSE。

因此准确表达是：

> 项目用 LangGraph 描述了 V2 工作流，并保留了图执行实现；当前默认的流式研究入口实际使用 `_run_simplified()` 手写阶段编排。

这不是文字游戏。面试或排错时，如果只说“LangGraph 正在执行”，就无法解释真实的事件顺序、检查点位置和 DataAnalyst 的执行位置。

---

## 2. 常见误解纠正

| 容易误解的说法 | 更准确的理解 |
|---|---|
| SSE 是 WebSocket | SSE 是服务器到浏览器的单向事件流；本项目的研究请求用它接收后端进度 |
| `ResearchState` 就是数据库 | 它是运行时共享状态；检查点服务才负责保存状态 |
| `ref` 里的数据变化页面会自动刷新 | `useRef` 变化不会自动触发渲染，需要 state 更新或版本计数器 |
| 安装了 LangGraph 就代表图正在执行 | 还要看 `run()` 实际调用哪条路径 |
| `final_report` 有内容就代表研究完成 | 还要经过 Critic，并由 `research_complete` 事件结束前端流程 |
| DataAnalyst 和 CodeWizard 是同一个 Agent | 前者偏结构化分析和图表配置，后者负责生成并执行 Python |

---

## 3. 一次真实研究请求的总图

以用户提问“新能源汽车行业未来三年的竞争格局”为例，默认流式路径可以画成：

```text
React Chat 页面
  │ POST /research/stream
  ▼
DeepResearchGraph.run()
  │ 创建初始 ResearchState，覆盖 max_iterations
  │ yield research_start
  ▼
_run_simplified()
  │ 每个 Agent 都在 asyncio.Queue 中产生消息
  ├─ phase=planning      → ChiefArchitect
  ├─ phase=researching   → DeepScout
  ├─ phase=analyzing     → DataAnalyst → CodeWizard
  ├─ phase=writing       → LeadWriter
  ├─ phase=reviewing     → CriticMaster
  │                         ├─ pass → completed
  │                         ├─ 缺证据 → re_researching → Scout → Writer
  │                         └─ 文字问题 → revising → Writer
  ▼
research_complete
  │ final_report、references、quality_score、统计信息
  ▼
React 更新报告、引用和研究详情面板
```

LangGraph 的图结构表达的是同一类阶段关系，但默认 `run()` 没有走 `self.graph.astream(...)`。

---

## 4. 后端状态如何一步步变化

### 4.1 初始状态：只有问题和空容器

`create_initial_state()` 创建：

```text
query = 用户问题
session_id = 当前会话
phase = init
iteration = 0
outline、facts、data_points、charts、final_report 等都是空容器
```

随后 `run()` 执行：

```python
state["max_iterations"] = self.max_iterations
```

所以运行时的最大迭代次数以配置对象为准，不要只看 `create_initial_state()` 中写死的默认值。

同时发送：

```json
{
  "type": "research_start",
  "query": "新能源汽车行业未来三年的竞争格局"
}
```

### 4.2 Planning：Architect 把问题拆成计划

Architect 读取 `query` 和搜索开关，调用 LLM 生成并解析规划结果，主要写入：

```text
outline
research_questions
key_entities
hypotheses
mind_map
knowledge_graph（初始化结构）
phase = planning
```

例如大纲可能包含“主要竞争者”“技术路线”“市场份额”和“未来三年变化”几个章节。每个章节会带有是否需要数据、是否需要图表和后续搜索查询等信息。

阶段结束后，`save_checkpoint_async()` 保存后端状态和 UI 状态，并记录 `planning` 步骤及章节数量。

### 4.3 Researching：Scout 把计划变成证据

Scout 读取 `outline` 和 `research_questions`，找到状态为 `pending` 的章节。当前代码每轮最多并行处理前三个待研究章节，然后搜索网页或本地知识库，分析结果并写入：

```text
facts
data_points（部分搜索分析可能先产生）
raw_sources
references
insights
knowledge_graph
```

它会通过消息队列发送搜索结果、事实观察和知识图谱事件。研究完成后，检查点统计事实数和来源数。

这里要记住一个工程边界：如果大纲章节多于每轮处理上限，Scout 可能只覆盖部分章节，而 Writer 仍会遍历完整大纲。报告存在，并不自动证明每一章都有足够证据。

### 4.4 Analyzing：DataAnalyst 和 CodeWizard 连续执行

手写流式路径明确执行两个 Agent：

```text
DataAnalyst
  事实 → 数据点、洞察、知识图谱、部分 ECharts 配置

CodeWizard
  数据点/分析要求 → LLM 生成 Python
  → compile 和危险模式检查
  → 受限 globals 中 exec
  → code_executions、charts
```

两者都可能产生图表，但输出含义不同：DataAnalyst 主要生成结构化分析结果，CodeWizard 负责实际计算和代码产生的图像或配置。

前端收到 `knowledge_graph`、`charts` 或单个 `chart` 事件后，把它们放到 `researchDetailsRef` 对应的 `analyzing` 详情中，并递增 `researchDataVersion`。

### 4.5 Writing：Writer 把素材组织成报告

Writer 读取 `outline`、`facts`、`data_points`、`charts`、`insights` 和 `references`，按大纲写入：

```text
draft_sections = {section_id: section_content}
final_report = 完整报告文本
```

写作结束后，代码保存 `writing` 检查点，并记录报告长度。此时报告已经存在，但状态仍要进入 `reviewing`，因为文字可能缺乏来源、存在逻辑问题或遗漏章节。

### 4.6 Reviewing：Critic 决定是否继续循环

Critic 读取报告和证据，写入：

```text
critic_feedback
quality_score
unresolved_issues
pending_search_queries（必要时）
```

它的路由规则可以用下面的决策表理解：

| 审核结果 | 下一阶段 |
|---|---|
| 通过 | `completed` |
| 缺少来源、数据过期或内容不完整，且需要新查询 | `re_researching`，再执行 Scout 和 Writer |
| 只是表述、结构或逻辑问题，不需要新证据 | `revising`，再次执行 Writer |
| 达到最大迭代次数 | 强制 `completed`，同时发送可能仍有问题的警告 |

因此 Critic 不只是评分器，它还承担流程路由器的职责。

---

## 5. 检查点保存的是什么

每个主要阶段后，`save_checkpoint_async()` 做两件事：

1. 从 `ResearchState` 生成当前 UI 可恢复数据，例如步骤、搜索结果、图表、知识图谱、报告和引用。
2. 调用 `_save_checkpoint()`，把 `state`、`ui_state`、`session_id`、`user_id` 和当前报告交给检查点服务。

这解释了为什么刷新页面后可以恢复研究详情：恢复的不只是最后一段报告，而是后端工作状态和前端展示所需的摘要状态。

但检查点不是实时数据库同步。Agent 执行期间的消息先在内存队列中流出，阶段结束时才保存一个阶段性快照。

---

## 6. 前端如何接住后端事件

### 6.1 `researchSteps`：步骤目录

当收到 `research_step` 事件时，前端按 `stepType` 查找步骤：

```text
找到 → 更新 status 和 stats
找不到 → 新增一个步骤
```

统计字段会从后端的 snake_case 转成前端使用的 camelCase，例如：

```text
results_count  → resultsCount
charts_count   → chartsCount
sections_count → sectionsCount
```

### 6.2 `researchDetailsRef`：步骤详情仓库

`research_step` 首次出现某个类型时，前端建立：

```text
Map.set("analyzing", {
  stepId: "analyzing",
  stepType: "analyzing",
  searchResults: [],
  charts: []
})
```

后续事件用相同的 `stepType` 查找并追加数据：

```text
search_results  → searching/researching.searchResults
knowledge_graph → analyzing.knowledgeGraph
charts/chart    → analyzing.charts
research_complete.final_report → writing.streamingReport
```

这就是后端事件类型和研究详情面板之间的映射关系。

### 6.3 为什么需要 `researchDataVersion`

代码直接修改 `researchDetailsRef.current` 里的对象，例如追加一个图表。React 不会因为 ref 内部对象被修改而重新渲染，所以代码还会执行：

```typescript
setResearchDataVersion(version => version + 1)
```

聚合研究数据的计算逻辑把 `researchDataVersion` 放在依赖数组中，版本变化后就会重新读取 Map。这个计数器不保存业务数据，它只负责通知 React：“详情引用里的内容变了，请重新计算”。

---

## 7. 一张状态演化表

| 阶段 | 主要读取 | 主要写入 | 主要事件/检查点 |
|---|---|---|---|
| planning | `query`、搜索开关 | `outline`、问题、实体、假设 | `phase`、规划消息、`planning` 检查点 |
| researching | `outline`、研究问题 | `facts`、`raw_sources`、`references`、洞察 | 搜索结果、图谱、`researching` 检查点 |
| analyzing | `facts`、`data_points` | 数据点、图谱、洞察、`charts`、`code_executions` | 图表/图谱事件、`analyzing` 检查点 |
| writing | 大纲、证据、分析产物 | `draft_sections`、`final_report` | 报告事件、`writing` 检查点 |
| reviewing | 报告、事实、数据点 | 反馈、分数、未解决问题、待搜索查询 | 审核消息、路由状态 |
| re_researching | `pending_search_queries` | 新事实、引用和报告素材 | 补充搜索、重新写作 |
| revising | 报告、Critic 反馈 | 修订后的章节和报告 | 修订消息 |

---

## 8. 这一课的练习

请先不要看源码，用自己的话回答：

1. 如果没有 `ResearchState`，Architect、Scout 和 Writer 之间需要怎样传递信息？为什么容易出错？
2. 为什么 `facts`、`data_points` 和 `final_report` 不能简单合并成一个字符串？
3. CriticMaster 遇到“缺少 2025 年官方数据”和“段落顺序混乱”时，分别应该走哪条路由？
4. 为什么收到一个图表后，前端既要修改 `researchDetailsRef`，又要更新 `researchDataVersion`？
5. 用一句话区分“LangGraph 图”和“当前默认的 `_run_simplified()`”。

下一课会逐个拆解 CodeWizard：LLM 生成代码、`compile()`、危险模式检查、`exec()`、输出捕获、重试，以及为什么它还不能算生产级沙箱。

