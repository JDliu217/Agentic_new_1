# DeepResearch 学习手册：第 94 课

## V1 与 V2：同一个项目中的两套研究实现

项目没有把旧研究实现完全删除，而是同时保留 V1 和 V2。理解版本边界，是判断“为什么看到的事件和课程不一样”的前提。

## 1. 接口默认值不同

文件：`backend/app/router/research_router.py`

### POST

`ResearchRequest.version` 默认是：

```text
v2
```

前端 `deepsearch()` 使用 POST `/research/stream`，没有显式传版本时，通常进入 V2。

### GET

GET `/research/stream` 的 `version` 查询参数默认是：

```text
v1
```

所以“同一个路径”由于请求方法不同，可能进入不同实现。

## 2. V1：ReAct 和工具执行器

主要文件：

```text
backend/app/service/dr_g.py
backend/app/service/react_controller.py
backend/app/service/tool_executor.py
```

V1 的主要思路是：

```text
问题
→ LLM 生成研究计划
→ 选择工具
→ 并行搜索或执行其他工具
→ 观察结果
→ 反思是否缺信息
→ 生成补充查询
→ 完成
```

ReActController 的循环事件包括：

```text
react_start
status
thought
plan
action
search_result_item
observation
react_complete
```

V1 更像“一个控制器调用多个工具”，中间结果保存在 `ReActContext` 和事件流中。

## 3. V2：六个专业 Agent 共享状态

主要文件：

```text
backend/app/service/deep_research_v2/service.py
backend/app/service/deep_research_v2/graph.py
backend/app/service/deep_research_v2/state.py
backend/app/service/deep_research_v2/agents/
```

V2 的主要思路是：

```text
ResearchState
→ ChiefArchitect
→ DeepScout
→ DataAnalyst
→ CodeWizard
→ LeadWriter
→ CriticMaster
```

主要事件包括：

```text
research_start
phase
research_step
outline
search_results
knowledge_graph
charts
code
code_result
chart
report_draft
review
research_complete
```

V2 重点是状态字段、阶段和 Agent 责任边界。

## 4. 两个版本的关键区别

| 维度 | V1 | V2 |
|---|---|---|
| 入口服务 | `ResearchService` | `DeepResearchV2Service` |
| 核心抽象 | ReActController + Tool | ResearchState + Agent |
| 规划方式 | 计划和工具查询 | ChiefArchitect 生成大纲 |
| 搜索过程 | 工具执行器并行查询 | DeepScout 研究章节 |
| 数据分析 | 工具或控制器链路 | DataAnalyst + CodeWizard |
| 写作和审核 | 旧流程或兼容逻辑 | LeadWriter + CriticMaster |
| 事件命名 | `search_result_item` 等 | `research_step`、`charts`、`report_draft` 等 |
| 版本默认 | GET 默认 | POST 默认 |

## 5. 为什么排错时必须先确认版本

如果你按 V2 的事件去排查 V1 请求，会得到错误结论。例如：

```text
V1 页面收到了 search_result_item
但你一直查 V2 的 search_results 分支
```

或者：

```text
GET 请求默认走 V1
但你以为它会创建 ResearchState 和六个 Agent
```

第一步永远是看：

```text
请求方法
请求体或 query 中的 version
Router 日志中的版本选择
```

## 6. 当前 V2 还有一个实现层次

V2 源码包含 LangGraph 构图和 `_run_with_langgraph()`，但当前 `run()` 明确调用 `_run_simplified()`。因此还要再区分：

```text
V2 设计：可以用 LangGraph 表达节点和条件边
V2 当前默认运行：手写简化流程 + asyncio.Queue
```

不能因为看到 `StateGraph` 就断言本次请求实际通过 LangGraph 执行。

## 7. 如何从事件判断版本

### 更像 V1

```text
react_start
plan
action
search_result_item
react_complete
```

### 更像 V2

```text
research_start
research_step
phase
outline
report_draft
research_complete
```

这只是快速判断，最终仍应以 Router 分支和服务日志为准。

## 8. 本课练习

请回答：

1. 为什么 POST 和 GET `/research/stream` 可能进入不同版本？
2. V1 的 `ReActContext` 与 V2 的 `ResearchState` 分别承担什么角色？
3. 如果日志出现 `react_start` 而没有 `research_start`，你先查哪一个 Router 参数？
