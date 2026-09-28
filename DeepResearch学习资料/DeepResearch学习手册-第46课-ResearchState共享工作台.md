# DeepResearch 学习手册：第 46 课

## ResearchState：六个 Agent 的共享工作台

如果把六个 Agent 看成六个岗位，`ResearchState` 就是它们共同维护的研究项目文件夹。它不是简单的聊天记录，而是有阶段、输入、产物、错误和恢复信息的结构化状态。

## 1. 状态从哪里开始

`create_initial_state(query, session_id, search_web, search_local)` 创建初始状态：

```text
query：用户问题
session_id：研究所属会话
phase：init
iteration：0
search_web / search_local：搜索开关
其余列表和字典：空容器
```

Router 会把请求中的 `search_modes` 转换成这两个布尔字段；V2 图流程还会把配置中的最大迭代次数写入状态。

## 2. 状态字段按五类理解

### 请求和控制

`query`、`session_id`、`phase`、`iteration`、`max_iterations` 决定“研究什么”和“现在走到哪一步”。

### 规划

`outline`、`key_entities`、`research_questions`、`hypotheses` 描述 ChiefArchitect 拆出的研究计划。

### 证据和分析

`facts`、`data_points`、`raw_sources`、`knowledge_graph`、`insights`、`charts` 保存搜索、结构化分析和图表产物。

### 写作和审核

`draft_sections`、`final_report`、`references`、`critic_feedback`、`unresolved_issues`、`quality_score` 保存报告和质量反馈。

### 运行记录

`logs`、`errors`、`messages` 记录排错信息和流式事件。`messages` 更偏向本次运行的消息传输，不等于数据库中的 `ChatMessage`。

## 3. 六个 Agent 怎样交接

```text
ChiefArchitect
  读 query
  写 outline / research_questions / hypotheses

DeepScout
  读 outline / research_questions / search flags
  写 facts / references / data_points

DataAnalyst
  读 facts / data_points
  写 knowledge_graph / insights / ECharts charts

CodeWizard
  读 data_points / 分析任务
  写 code_executions / 图片 charts

LeadWriter
  读 outline / facts / insights / charts / references
  写 draft_sections / final_report

CriticMaster
  读 final_report / facts / outline
  写 critic_feedback / quality_score / pending_search_queries
```

这里的“读写”是职责上的重点字段，不代表 Agent 绝不会访问其他字段。

## 4. 为什么不用 Agent 之间直接传字符串

直接传字符串会出现：

- 下一个 Agent 不知道数据类型和来源。
- 图表、引用、错误和报告混在一段文本里。
- 无法方便保存检查点。
- 前端无法稳定识别“搜索结果”和“图表事件”。
- 审核发现问题后难以定位是哪一章、哪一个事实。

结构化状态让字段有明确用途，也让数据库恢复和前端展示有稳定入口。

## 5. 阶段状态机

设计中的阶段包括：

```text
init
→ planning
→ researching
→ analyzing
→ writing
→ reviewing
→ completed
```

审核不通过时可能进入：

```text
reviewing
→ re_researching
→ writing
```

或：

```text
reviewing
→ revising
→ writing
```

实际手写流程在每个主要阶段前后修改 `state["phase"]`，并在阶段完成时保存检查点。

## 6. ResearchState、消息队列和检查点的区别

```text
ResearchState
  当前研究的完整内存状态

asyncio.Queue
  当前请求中，把 Agent 事件实时交给 SSE

ResearchCheckpoint.state_json
  后端状态的持久化快照

ResearchCheckpoint.ui_state_json
  前端研究面板的恢复数据
```

如果只保存队列，浏览器断开后已经发送的事件无法恢复；如果只保存状态而不发 SSE，用户又无法实时看到过程。

## 7. 一个状态演化例子

用户问题：`新能源汽车未来三年的竞争格局是什么？`

```text
初始：query 有值，outline/facts/charts 为空

规划后：outline 有章节，research_questions 有子问题

搜索后：facts/references/data_points 增加

分析后：knowledge_graph/insights/charts 增加

写作后：draft_sections/final_report 有内容

审核后：quality_score/critic_feedback 决定完成、补搜或修订
```

## 8. 本课练习

1. 为什么 `messages` 不能直接等同于 `ChatMessage`？
2. 如果 `facts` 有数据但 `charts` 为空，应该先查哪个 Agent？
3. 如果 `final_report` 有内容但刷新页面后右侧面板为空，应该检查哪一种检查点数据？
4. 为什么 `phase` 是排错时的重要字段？

## 9. 关键源码

- `backend/app/service/deep_research_v2/state.py:17-205`
- `backend/app/service/deep_research_v2/graph.py:380-690`
- `backend/app/service/deep_research_v2/agents/architect.py`
- `backend/app/service/deep_research_v2/agents/scout.py`
- `backend/app/service/deep_research_v2/agents/data_analyst.py`
- `backend/app/service/deep_research_v2/agents/wizard.py`
- `backend/app/service/deep_research_v2/agents/writer.py`
- `backend/app/service/deep_research_v2/agents/critic.py`

