# DeepResearch 学习手册·第 15 课

## ResearchState 状态演化与 Agent 交接

本课的目标是让你能回答：一个 Agent 做完以后，究竟把什么交给了下一个 Agent？

不要只背“Architect 负责规划、Scout 负责搜索”。真正理解项目，需要能指出共享状态中哪些字段发生了变化。

源码：`D:\课\s4-6\industry_information_assistant\backend\app\service\deep_research_v2\state.py`

---

## 1. 状态不是最终答案

`ResearchState` 是一个 `TypedDict`，可以把它想成研究项目的共享工作台：

```text
用户问题和流程控制
        ↓
规划字段
        ↓
证据和数据字段
        ↓
图表、洞察和报告字段
        ↓
审核反馈和下一步路由
```

它同时承担三种职责：

1. 保存 Agent 之间的交接结果。
2. 保存流程控制信息，例如当前阶段和迭代次数。
3. 保存最终报告和前端需要展示的产物。

因此，`state` 不是一个“聊天上下文字符串”，而是结构化的工作记忆。

---

## 2. 初始状态

`create_initial_state(query, session_id, search_web, search_local)` 创建的核心字段如下：

```python
{
    "query": "用户的问题",
    "session_id": "会话 ID",
    "phase": "init",
    "iteration": 0,
    "max_iterations": 3,
    "search_web": True,
    "search_local": False,
    "outline": [],
    "research_questions": [],
    "facts": [],
    "data_points": [],
    "raw_sources": [],
    "charts": [],
    "code_executions": [],
    "insights": [],
    "draft_sections": {},
    "final_report": "",
    "references": [],
    "critic_feedback": [],
    "unresolved_issues": 0,
    "quality_score": 0.0,
    "pending_search_queries": [],
    "logs": [],
    "errors": [],
    "messages": []
}
```

注意：初始状态中的 `max_iterations` 是 3；`DeepResearchGraph.run()` 随后会用配置中的 `self.max_iterations` 覆盖它。运行时应以覆盖后的值为准。

---

## 3. Architect 做完后：从问题变成计划

`ChiefArchitect._initial_planning()` 调用 LLM 并解析 JSON，然后写入：

```text
key_entities
mind_map
research_questions
hypotheses
knowledge_graph（初始化为空图）
outline
```

每个 `outline` 章节会被规范化为类似结构：

```json
{
  "id": "sec_1",
  "title": "市场规模",
  "description": "分析市场规模和增长速度",
  "section_type": "quantitative",
  "requires_data": true,
  "requires_chart": true,
  "priority": 1,
  "search_queries": ["2024 储能市场规模"],
  "status": "pending"
}
```

规划完成后：

```text
phase: init → planning
outline: [] → 多个 pending 章节
research_questions: [] → 子问题列表
```

同时，Architect 发送：

- `research_step`：规划开始和完成。
- `thought`：面向过程展示的思考说明。
- `outline`：大纲和研究问题。

这些事件放入 `state["messages"]`，并在存在消息队列时实时推给前端。

---

## 4. Scout 做完后：从计划变成证据

`DeepScout.process()` 先找到 `status == "pending"` 的章节，每轮最多并行处理前三个章节：

```python
for section in pending_sections[:3]:
    tasks.append(self._research_section(state, section))
await asyncio.gather(*tasks)
```

每次搜索和 LLM 分析成功后，Scout 可能写入：

```text
facts
data_points
knowledge_graph
insights
```

一个事实大致包含：

```json
{
  "id": "fact_xxx",
  "content": "结构化事实内容",
  "source_url": "https://...",
  "source_name": "来源名称",
  "source_type": "official",
  "credibility_score": 0.85,
  "related_sections": ["sec_1"],
  "verified": false
}
```

Scout 还会把搜索结果和分析结果通过事件发送：

- `search_results`：前端搜索结果列表。
- `knowledge_graph`：知识图谱增量。
- `observation`：新增事实、数据点和来源质量。
- `action`：执行了哪种搜索工具。

### 4.1 Scout 的递归搜索

LLM 分析搜索结果后，可能提出：

- `source_tracing_queries`：追溯原始数据源。
- `follow_up_queries`：追踪新发现的线索。

只要当前迭代次数允许，Scout 会继续执行深度搜索。这里的“深度”不是模型自动变聪明，而是代码根据分析结果追加查询，并限制递归深度。

---

## 5. DataAnalyst 做完后：从证据变成结构化分析

`DataAnalyst._analyze_data()` 依次做三件事：

```text
事实
 → _extract_data()
 → _build_knowledge_graph()
 → _generate_charts()
```

### 5.1 提取数据点和洞察

`_extract_data()` 取前 20 条事实交给 LLM，解析返回的 `data_points` 和 `insights`：

```python
state["data_points"].append(dp)
state["insights"].extend(result["insights"])
```

一个数据点通常包括：

```text
id、name、value、unit、year、source、confidence
```

### 5.2 构建知识图谱

`_build_knowledge_graph()` 把事实内容交给 LLM，得到：

```json
{
  "nodes": [],
  "edges": []
}
```

代码还会根据实体重要性计算节点大小，然后写入：

```python
state["knowledge_graph"] = knowledge_graph
```

### 5.3 生成 ECharts 配置

`_generate_charts()` 根据数据点、时间序列和分布信息生成图表配置。生成成功后：

```python
state["charts"].extend(charts)
```

随后发送 `charts` 事件。此时图表仍是结构化配置，前端再交给 ECharts 渲染。

---

## 6. CodeWizard 做完后：执行可验证计算

手写流式流程中，CodeWizard 紧接 DataAnalyst 执行。

它读取：

```text
state["data_points"]
state["outline"]
state["facts"]
```

然后：

```text
LLM 生成 Python
→ compile()
→ 危险模式检查
→ 受限 globals 中 exec()
→ 捕获 stdout/stderr
→ 保存图像和代码执行记录
```

主要写入：

```text
state["charts"]
state["code_executions"]
```

DataAnalyst 负责“从事实提取数据、生成分析配置”；CodeWizard 负责“用代码执行计算和生成图像”。两者可能都产生图表，但职责不同。

---

## 7. Writer 做完后：从素材变成报告

`LeadWriter._write_report()` 遍历 `state["outline"]`，对尚未完成的章节调用 `_write_section()`，然后整合报告。

它读取：

```text
outline
facts
data_points
charts
insights
references
```

它写入：

```text
draft_sections
final_report
references
```

写作结束时：

```text
phase: writing → reviewing
```

注意：`final_report` 是报告文本；`research_complete` 是后端最后发出的业务事件。报告文本存在，不代表审核已经结束。

---

## 8. Critic 做完后：从报告变成路由决定

`CriticMaster.process()` 先检查当前是否为 `reviewing`，再审核报告。

它写入：

```text
critic_feedback
quality_score
unresolved_issues
```

如果发现信息缺失，还会写入：

```text
pending_search_queries
```

然后根据审核结果更新 `phase`：

```text
pass                  → completed
需要新证据             → re_researching
只需修改文字           → revising
达到最大迭代次数        → completed（并警告可能仍有问题）
```

所以 Critic 不只是“打分 Agent”，还是工作流路由器。

---

## 9. 状态演化示例

以“分析储能行业市场规模”为例：

```text
初始：
phase=init, outline=[], facts=[], charts=[], final_report=""

规划后：
phase=planning, outline=[sec_1, sec_2, ...], research_questions=[...]

搜索后：
phase=researching, facts=[fact_1, fact_2, ...], data_points=[dp_1, ...]

分析后：
phase=analyzing, knowledge_graph={...}, charts=[chart_1], insights=[...]

写作后：
phase=reviewing, draft_sections={...}, final_report="..."

审核后：
phase=completed 或 re_researching 或 revising
```

每一步都不是把上一步结果替换掉，而是在共享状态中添加或更新字段。

---

## 10. 参数接收不等于参数贯通

当前有一个必须记住的集成边界：

```text
ResearchRequest.kb_name
→ research_router
→ DeepResearchV2Service.research(kb_name=...)
```

但是 `DeepResearchV2Service.research()` 调用 `self.graph.run()` 时，没有继续传入 `kb_name`；`ResearchState` 也没有 `kb_name` 字段。与此同时，DeepScout 本地搜索固定查询 `knowledge_base` 集合。

因此不能仅凭函数签名说“V2 已经按指定知识库检索”。准确说法是：

> 请求层和 Service 层接收了 `kb_name`，但当前 V2 图状态和 DeepScout 检索集合之间还没有形成完整的知识库选择契约。

---

## 11. 练习：填状态变化表

问题：`state` 在以下阶段至少有哪些变化？

| 阶段 | 至少新增或更新的字段 | 产生的事件 |
|---|---|---|
| planning |  |  |
| researching |  |  |
| analyzing |  |  |
| writing |  |  |
| reviewing |  |  |
| re_researching |  |  |

### 我的答案

<!-- 在这里填写你的表格 -->


## 12. 面试题

1. 为什么 `ResearchState` 使用结构化字段，而不是让 Agent 之间传一段自然语言？
2. `facts`、`data_points` 和 `charts` 的关系是什么？
3. DataAnalyst 和 CodeWizard 的职责如何区分？
4. Critic 为什么既是审核者又是路由器？
5. `kb_name` 已经出现在请求模型里，为什么仍不能说 V2 本地知识库选择已经完整接通？
6. 为什么 `final_report` 已生成后还要经过 Critic？

### 我的面试回答

<!-- 用自己的话回答，下一次根据答案进行批改 -->

